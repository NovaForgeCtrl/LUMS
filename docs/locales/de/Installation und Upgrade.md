# LUMS Installationsanleitung

## Linux Update Management Server

**Projekt:** LUMS
**Slogan:** Linux Update Management ohne das Rauschen.
**Repository:** `NovaForgeCtrl/LUMS`

---

## Erste Schritte: Verstehen Sie die Installation, bevor Sie beginnen

Diese Anleitung beschreibt eine vollständige Serverinstallation, einschließlich fortgeschrittener Wartungs- und Verifikationsverfahren. Sie ist **kein einzelnes Skript, das ohne Prüfung ausgeführt werden sollte**: Der Servername, das TLS-Zertifikat, die Secret-Datei, das Backup-Ziel, das Netzwerk und die Datenbank unterscheiden sich zwischen Installationen.

### Was wird installiert?

* **LUMS-Server:** die Weboberfläche und API, ausgeführt in einem Docker-Container.
* **Nginx:** nimmt externe HTTPS-Verbindungen an und leitet sie lokal an den Container weiter.
* **Daten-Volume:** enthält die SQLite-Datenbank. Dieses Volume muss Upgrades überleben und darf während eines normalen Container-Austauschs niemals gelöscht werden.
* **Secret-Datei:** schützt unter anderem Anwendungssitzungen. Niemals in das Git-Repository, ein Docker-Image oder eine Chat-Nachricht legen.
* **LUMS Agent und Watcher:** werden separat auf verwalteten Linux-Clients installiert. Ein funktionierender Server allein aktualisiert keine Clients.

| Begriff | Bedeutung |
| --- | --- |
| Terminal / Shell | Ein Textfenster, in dem Sie Linux-Befehle eingeben. |
| `sudo` | Führt den folgenden Befehl mit Administratorrechten aus. Linux kann nach Ihrem Passwort fragen. |
| Host | Der Linux-Computer, auf dem Docker und der LUMS-Server laufen. |
| Container | Ein isolierter Prozess, der die LUMS-Webanwendung ausführt. |
| Image | Eine vorbereitete Vorlage, die Docker zum Starten eines Containers verwendet. |
| Volume | Persistenter Docker-Speicher, der erhalten bleibt, wenn ein Container ersetzt wird. |
| Platzhalter | Text wie `LUMS-SERVER`, der durch Ihren tatsächlichen Wert ersetzt werden muss. |

### Nur Tests ausführen (dies installiert keinen Server)

Diese Schritte eignen sich für Debian 13, um den Quellcode auszuchecken und Tests lokal auszuführen. Sie erstellen **keinen** produktiven Server, der über das Netzwerk erreichbar ist, und installieren keinen Agent auf einem anderen Computer. `sudo` wird nur benötigt, um Debian-Pakete zu installieren.

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
git clone https://github.com/NovaForgeCtrl/LUMS.git ~/LUMS
cd ~/LUMS
python3 -m venv .venv-test
./.venv-test/bin/python -m pip install -r server/requirements.txt -r requirements-dev.txt
./.venv-test/bin/pytest -q
```

`apt update` aktualisiert Paketlisten; es aktualisiert nicht alle installierten Programme. Die Python-virtualenv `.venv-test` hält Testabhängigkeiten vom Rest des Systems getrennt. Ein erfolgreicher Testlauf endet mit Exit-Code `0`; die Anzahl der Tests kann sich ändern, während das Projekt wächst. Wenn das Erstellen der Umgebung fehlschlägt, prüfen Sie, ob `python3-venv` installiert ist. Wenn ein Test fehlschlägt, speichern Sie den vollständigen Fehler und lesen Sie die [Fehlerbehebungsanleitung](Fehlersuche.md); löschen Sie keine Produktionsdaten.

Für eine echte Installation fahren Sie mit den nummerierten Abschnitten fort und lesen Sie zuerst die Sicherheits- und Backup-Anweisungen. Wenn LUMS bereits läuft, verwenden Sie das Upgrade-Verfahren in [`administration.md`](<Administration und Backups.md>), nicht das Erstinstallationsverfahren.

---

# 1. Überblick

LUMS ist eine zentrale Linux-Update-Management-Plattform für kontrollierte Update-Verteilung, Client-Berichterstattung, Paketverwaltung, Ausführung von Update-Jobs, Ergebnisvalidierung und auditierbare Administration.

Die aktuelle Architektur trennt den Management-Server von den verwalteten Linux-Clients.

Der Server bietet:

* Webbasierte Administration
* Client-Verwaltung
* Client-Authentifizierung
* Paketinventar
* Berichterstattung über verfügbare Updates
* Paketsuche
* Paketinstallation und -entfernung
* Update-Job-Verwaltung
* Validierung von Job-Ergebnissen
* Update-Verlauf
* Rollenbasierte Zugriffskontrolle
* Audit-Logging
* Persistenter Zustand auf SQLite-Basis

Linux-Clients bieten:

* Systeminformationen
* Inventar installierter Pakete
* Erkennung verfügbarer Updates
* Paketoperationen
* Ausführung von Update-Jobs
* Erkennung des Idle-Zustands
* Job-Checkpointing und Wiederherstellung
* Reboot-Erkennung
* Ergebnisberichterstattung

Die aktuelle Implementierung unterstützt:

```text
Debian / Ubuntu
    └── APT / dpkg

Arch Linux
    └── pacman
```

---

# 2. Architektur

Die Produktionsarchitektur ist:

```text
                         LUMS Server
                              │
                              │ HTTPS :443
                              ▼
                       ┌──────────────┐
                       │    Nginx     │
                       │  TLS / Proxy │
                       └──────┬───────┘
                              │
                              │ HTTP
                              ▼
                       127.0.0.1:5050
                              │
                              ▼
                    ┌───────────────────┐
                    │   Docker: lums    │
                    │                   │
                    │   Gunicorn        │
                    │   Flask :5000     │
                    │   SQLite          │
                    └─────────┬─────────┘
                              │
                              ▼
                         lums-data
                              │
                              ▼
                   /var/lib/lums/lums.db


        Linux Client
              │
              │ HTTPS + Bearer Token
              ▼
         LUMS API
              │
              ├── Report
              ├── Package Search
              ├── Job Retrieval
              └── Job Result
```

Die LUMS-Anwendung ist **nicht dafür vorgesehen, direkt dem Netzwerk ausgesetzt zu werden**.

Der Anwendungscontainer ist gebunden an:

```text
127.0.0.1:5050 → container:5000
```

Nginx ist der externe HTTPS-Einstiegspunkt.

Port `5000` wird nicht direkt veröffentlicht.

Port `5050` muss ausschließlich auf localhost beschränkt bleiben.

---

# 3. Anwendungskomponenten

Eine vollständige LUMS-Installation besteht aus mehreren Komponenten.

## 3.1 LUMS-Server

Der Server enthält:

```text
Flask
Gunicorn
SQLite
Web UI
REST API
Authentication
RBAC
Audit logging
Job management
Package management
```

Die Anwendung läuft im Docker-Container:

```text
lums
```

Die persistente Datenbank wird außerhalb des beschreibbaren Anwendungsdateisystems des Containers gespeichert:

```text
lums-data:/var/lib/lums/lums.db
```

---

## 3.2 Nginx

Nginx bietet:

```text
HTTPS termination
TLS certificate handling
HTTP → HTTPS redirect
Reverse proxy
External network entry point
```

Der vorgesehene Anfragepfad ist:

```text
Browser
   │
   │ HTTPS
   ▼
Nginx
   │
   │ localhost HTTP
   ▼
127.0.0.1:5050
   │
   ▼
LUMS
```

Die Flask/Gunicorn-Anwendung sollte nicht direkt dem LAN ausgesetzt werden.

---

## 3.3 Linux-Agent

Der LUMS Agent läuft auf jedem verwalteten Linux-Client.

Die aktuelle Agent-Version ist:

```text
1.7.0
```

Der Agent ist verantwortlich für:

```text
System information
Installed packages
Available updates
Client reporting
Job retrieval
Job claiming
Package operations
Result reporting
Reboot detection
```

Der Agent kommuniziert mit dem LUMS-Server über HTTPS und einen client-spezifischen Bearer-Token.

---

## 3.4 Execution Watcher

Der Execution Watcher ist für die kontrollierte Ausführung von Update-Jobs verantwortlich.

Die aktuelle Watcher-Version ist:

```text
1.2.1
```

Der Watcher übernimmt:

```text
Pending-job detection
Idle-state checks
Atomic job claiming
Update execution
Checkpoint handling
Interrupted-job recovery
Result processing
```

Der Watcher ist absichtlich von der gewöhnlichen Client-Berichterstattung getrennt.

---

# 4. Sicherheitsmodell

Die Installation muss die LUMS-Sicherheitsbasis erhalten.

Der Produktionsserver verwendet:

```text
HTTPS
Bearer-token client authentication
Role-based web authorization
CSRF protection
Audit logging
Read-only container root filesystem
Dropped Linux capabilities
no-new-privileges
Non-root application user
Localhost-only application port
Persistent Docker volume
Read-only secret mount
```

Der Docker-Container läuft als unprivilegierter Benutzer:

```text
lums
```

mit UID:

```text
10001
```

Der Container darf nicht im privilegierten Modus laufen.

Das Root-Dateisystem muss schreibgeschützt bleiben.

Die Anwendung darf keinen Schreibzugriff auf ihr Anwendungsverzeichnis benötigen.

Persistente Anwendungsdaten werden über das dedizierte Docker-Volume gespeichert.

---

# 5. Aktuelles RBAC-Modell

LUMS bietet derzeit drei Web-Rollen:

```text
administrator
operator
viewer
```

## Administrator

Administratoren können administrative Operationen durchführen, einschließlich:

```text
View clients
View installed software
View available updates
Create and execute update jobs
View update history
Use package management
Use system maintenance
Create and disable clients
Rotate client tokens
Manage users
Manage roles
```

---

## Operator

Operatoren können operative Verwaltungsaufgaben durchführen:

```text
View clients
View installed software
View available updates
Create and execute update jobs
View update history
Use package management
Use system maintenance
```

Operatoren haben keinen Zugriff auf:

```text
User management
Role management
Client creation/disabling
Client-token rotation
```

---

## Viewer

Viewer haben absichtlich eingeschränkten Zugriff.

Ein Viewer kann auf Folgendes zugreifen:

```text
Clients
Installed software
```

Die folgenden Managementbereiche sind für die Viewer-Oberfläche ausgeblendet und serverseitig geschützt:

```text
Available updates
Update Jobs
Update History
Package Management
System Maintenance
```

Das Ausblenden in der UI ist daher nicht die Sicherheitsgrenze.

Serverseitige Autorisierung bleibt verpflichtend.

---

# 6. Installationsanforderungen

## 6.1 LUMS-Server

Die aktuelle Bereitstellung erfordert einen Linux-Host mit:

```text
Docker Engine
Git
Nginx
OpenSSL
Network connectivity
Persistent storage
```

Der Server muss genügend Speicher haben für:

```text
Docker images
SQLite database
Application data
Logs
Backups
```

Die LUMS-Anwendung selbst läuft in Docker.

---

## 6.2 Linux-Clients

Verwaltete Linux-Clients erfordern:

```text
Python 3
systemd
Supported package manager
Network connectivity to the LUMS server
Valid client token
Trusted TLS certificate
```

Unterstützte Paketverwaltungsfamilien:

```text
Debian / Ubuntu
    APT / dpkg

Arch Linux
    pacman
```

Der Client muss den LUMS-HTTPS-Endpunkt erreichen können.

---

# 7. Empfohlenes Verzeichnislayout

Der empfohlene serverseitige Repository-Speicherort ist:

```text
/opt/lums-public/
```

Das Repository enthält den Anwendungsquellcode, den Agent-Quellcode und Tests.

Eine typische Installation verwendet:

```text
/opt/lums-public/
    ├── agent/
    ├── server/
    ├── tests/
    ├── Dockerfile
    ├── requirements.txt
    └── requirements-dev.txt
```

Host-seitige Konfiguration wird außerhalb des Repositories gehalten:

```text
/etc/lums/
    ├── secrets/
    │   └── lums_secret
    └── tls/
        ├── lums.crt
        └── lums.key
```

Persistente Anwendungsdaten werden gespeichert in:

```text
lums-data:/var/lib/lums
```

Die SQLite-Datenbank ist:

```text
/var/lib/lums/lums.db
```

Die Datenbank darf niemals innerhalb des Git-Arbeitsbaums gespeichert werden.

Secrets und privates TLS-Material müssen ebenfalls außerhalb des Repositories bleiben.

---

# 8. Repository-Vorbereitung

Klonen Sie das Repository in das vorgesehene Installationsverzeichnis:

```bash
sudo mkdir -p /opt
cd /opt

sudo git clone \
    https://github.com/NovaForgeCtrl/LUMS.git \
    lums-public
```

Betreten Sie das Repository:

```bash
cd /opt/lums-public
```

Prüfen Sie den Arbeitsbaum:

```bash
git status
```

Prüfen Sie die aktuelle Revision:

```bash
git log -1 --oneline --decorate
```

Für kontrollierte Bereitstellungen sollte der exakte Commit, der für die Installation verwendet wird, aufgezeichnet werden.

Bauen Sie keine Produktionsimages aus einem unbekannten oder nicht verifizierten Arbeitsbaum.

---

# 9. Repository-Sicherheitsprüfung

Bevor Sie das Produktionsimage bauen, stellen Sie sicher, dass keine sensiblen Dateien in das Repository gelangt sind.

Überprüfen Sie den Arbeitsbaum:

```bash
git status --short
```

Überprüfen Sie ignorierte Dateien, wo angebracht:

```bash
git status --ignored --short
```

Das Repository darf nicht enthalten:

```text
Production database files
Private TLS keys
Application secrets
Client tokens
Credential dumps
Backup databases
Runtime logs
Temporary backup files
```

Das Projekt verwendet Repository-Ignore-Regeln, um zu verhindern, dass gängige Backup-Artefakte versehentlich verfolgt werden.

Bevor Sie Änderungen committen, prüfen Sie die gestagte Dateiliste sorgfältig.

---

# 10. Host-Konfigurationsverzeichnisse vorbereiten

Erstellen Sie die erforderlichen host-seitigen Verzeichnisse:

```bash
sudo install -d -m 700 /etc/lums
sudo install -d -m 700 /etc/lums/secrets
sudo install -d -m 700 /etc/lums/tls
```

Das Secret-Verzeichnis enthält das Anwendungssecret.

Das TLS-Verzeichnis enthält das TLS-Zertifikat und den privaten Schlüssel.

Der Schutz dieser Verzeichnisse reduziert das Risiko einer versehentlichen Offenlegung.

Prüfen Sie:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums \
    /etc/lums/secrets \
    /etc/lums/tls
```

---

# 11. Anwendungssecret erstellen

Das LUMS-Anwendungssecret wird auf dem Host gespeichert und nicht direkt in das Docker-Image eingebettet.

Der Produktionspfad des Secrets ist:

```text
/etc/lums/secrets/lums_secret
```

Erzeugen Sie ein zufälliges Secret:

```bash
sudo sh -c 'umask 077 && openssl rand -hex 32 > /etc/lums/secrets/lums_secret'
```

Schützen Sie die resultierende Datei:

```bash
sudo chmod 600 \
    /etc/lums/secrets/lums_secret
```

Prüfen Sie die Berechtigungen, ohne das Secret anzuzeigen:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/secrets/lums_secret
```

Erwartet:

```text
600
```

Das Secret darf niemals:

```text
Committed to Git
Printed into logs
Included in the Docker image
Placed into screenshots
Published in issues
Included in documentation
```

Der Container erhält das Secret über einen schreibgeschützten Bind-Mount.

---

# 12. TLS-Material vorbereiten

LUMS verwendet HTTPS für den externen Zugriff.

Die empfohlenen host-seitigen Speicherorte sind:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Installieren Sie das entsprechende Zertifikat und den privaten Schlüssel, bevor Sie Nginx konfigurieren.

Schützen Sie den privaten Schlüssel:

```bash
sudo chmod 600 \
    /etc/lums/tls/lums.key
```

Das Zertifikat darf für den Nginx-Dienst lesbar sein:

```bash
sudo chmod 644 \
    /etc/lums/tls/lums.crt
```

Prüfen Sie:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

Der private Schlüssel darf niemals in Git committet oder in das Docker-Image aufgenommen werden.

---

# 13. Installationsprinzip

Die Installation sollte in kontrollierten Stufen erfolgen:

```text
Repository
    ↓
Host configuration
    ↓
Application secret
    ↓
TLS material
    ↓
Docker image
    ↓
Persistent volume
    ↓
Hardened container
    ↓
Nginx / HTTPS
    ↓
Administrator
    ↓
Server validation
    ↓
Linux clients
```

Verbinden Sie keine Produktionsclients, bevor der Server seine eigenen Validierungsprüfungen bestanden hat.

Die folgenden Abschnitte fahren mit der Docker-Image-Erstellung und der gehärteten Produktionsbereitstellung fort.

# 14. Das LUMS-Docker-Image bauen

Bevor Sie das Produktionsimage bauen, stellen Sie sicher, dass sich das Repository im vorgesehenen Zustand befindet.

Betreten Sie das Repository:

```bash
cd /opt/lums-public
```

Führen Sie die Testsuite aus, bevor Sie ein Produktionsimage erstellen:

```bash
./.venv-test/bin/pytest -q
```

Es wird erwartet, dass die Testanzahl wächst, während sich das Projekt weiterentwickelt.

Die wichtige Anforderung ist, dass die relevante Testsuite vor der Bereitstellung erfolgreich abgeschlossen wird.

Bauen Sie das Docker-Image:

```bash
sudo docker build \
    -t lums:latest \
    .
```

Prüfen Sie, dass das Image existiert:

```bash
sudo docker image ls lums
```

Inspizieren Sie das Image:

```bash
sudo docker image inspect lums:latest
```

Das Produktionsimage basiert auf einem gepinnten Python-3.13-Slim-Basisimage.

Das Dockerfile verwendet außerdem gepinnte Produktionsabhängigkeiten, wo erforderlich.

---

# 15. Den Docker-Build überprüfen

Bevor Sie das Image bereitstellen, überprüfen Sie die Build-Ausgabe auf unerwartete Fehler oder Warnungen.

Prüfen Sie das resultierende Image:

```bash
sudo docker inspect \
    lums:latest
```

Prüfen Sie den konfigurierten Anwendungsbenutzer:

```bash
sudo docker image inspect \
    lums:latest \
    --format '{{.Config.User}}'
```

Die Anwendung soll laufen als:

```text
lums
```

Die Anwendung darf während der normalen Ausführung keine Root-Privilegien benötigen.

Überprüfen Sie das Dockerfile, wenn Sie den Build-Prozess ändern:

```bash
sed -n '1,240p' Dockerfile
```

Fügen Sie keine Secrets, Zertifikate oder Produktionsdatenbanken zum Docker-Build-Kontext hinzu.

Das Repository enthält eine `.dockerignore`-Datei, um das Risiko zu reduzieren, dass Laufzeitartefakte versehentlich in das Image aufgenommen werden.

---

# 16. Das persistente Docker-Volume erstellen

Erstellen Sie das persistente LUMS-Daten-Volume:

```bash
sudo docker volume create lums-data
```

Prüfen Sie:

```bash
sudo docker volume inspect lums-data
```

Das Volume speichert persistente Anwendungsdaten:

```text
lums-data
    ↓
/var/lib/lums
    ↓
/var/lib/lums/lums.db
```

Das Container-Dateisystem selbst darf nicht als persistenter Anwendungsspeicher behandelt werden.

Die Datenbank überlebt daher den Container-Austausch, solange das Volume `lums-data` erhalten bleibt.

> [!IMPORTANT]
> Entfernen Sie `lums-data` niemals während eines normalen Anwendungs-Upgrades.

Das Entfernen des Volumes entfernt die darin gespeicherte SQLite-Datenbank.

---

# 17. Das persistente Volume prüfen

Bevor Sie LUMS starten, bestätigen Sie, dass das Volume existiert:

```bash
sudo docker volume inspect \
    lums-data
```

Das Volume kann auch über Docker geprüft werden:

```bash
sudo docker volume ls | grep lums-data
```

Ein neu erstelltes Volume enthält normalerweise noch keine Datenbank.

Die Datenbank wird von der LUMS-Anwendung während der Bereitstellung initialisiert.

---

# 18. Produktionscontainer-Konfiguration

Der Produktionscontainer verwendet mehrere Sicherheitskontrollen gleichzeitig.

Die erwartete Laufzeitbasis ist:

```text
Non-root user
Read-only root filesystem
All Linux capabilities dropped
no-new-privileges
No privileged mode
Localhost-only application binding
Read-only application-secret mount
Persistent writable data volume
Dedicated /tmp tmpfs
```

Der Anwendungsport wird nur auf localhost veröffentlicht:

```text
127.0.0.1:5050 → container:5000
```

Der externe HTTPS-Endpunkt wird von Nginx bereitgestellt.

---

# 19. Den gehärteten LUMS-Container starten

Bevor Sie einen neuen Produktionscontainer starten, stellen Sie sicher, dass nicht bereits ein anderer Container namens `lums` läuft:

```bash
sudo docker ps \
    --filter name=lums
```

Wenn eine bestehende Bereitstellung ersetzt wird, bewahren Sie den bestehenden Container auf, bis das neue Image validiert wurde.

Starten Sie den gehärteten Container:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --security-opt=no-new-privileges:true \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --tmpfs /run:rw,noexec,nosuid,size=16m \
    -p 127.0.0.1:5050:5000 \
    -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
    -v lums-data:/var/lib/lums \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    lums:latest
```

Das Anwendungssecret wird schreibgeschützt gemountet.

Die SQLite-Datenbank wird im persistenten Volume gespeichert.

Das Root-Dateisystem ist schreibgeschützt.

Alle Linux-Capabilities werden verworfen.

Die Sicherheitsoption `no-new-privileges` verhindert, dass Prozesse innerhalb des Containers zusätzliche Privilegien erlangen.

---

# 20. Den Containerzustand prüfen

Prüfen Sie den laufenden Container:

```bash
sudo docker ps \
    --filter name=lums
```

Erwarteter Zustand:

```text
Up ...
```

Prüfen Sie den Containerzustand direkt:

```bash
sudo docker inspect \
    --format '{{.State.Status}}' \
    lums
```

Erwartet:

```text
running
```

Inspizieren Sie die letzten Logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Anwendungsstartfehler müssen behoben werden, bevor Sie mit der Installation fortfahren.

---

# 21. Container-Sicherheit prüfen

Inspizieren Sie die effektive Laufzeit-Sicherheitskonfiguration:

```bash
sudo docker inspect lums \
    --format='User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} Privileged={{.HostConfig.Privileged}} CapDrop={{json .HostConfig.CapDrop}} SecurityOpt={{json .HostConfig.SecurityOpt}}'
```

Die erwartete Basis ist:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

Die genaue Formatierung der Docker-Ausgabe kann variieren.

Die effektive Konfiguration ist entscheidend.

---

# 22. Den Anwendungsport prüfen

Prüfen Sie den veröffentlichten Docker-Port:

```bash
sudo docker port lums
```

Erwartet:

```text
5000/tcp -> 127.0.0.1:5050
```

Das Folgende ist für die Produktionsanwendung **nicht** akzeptabel:

```text
0.0.0.0:5050
```

oder:

```text
0.0.0.0:5000
```

Die Anwendung ist absichtlich nur über den lokalen Reverse-Proxy-Pfad erreichbar.

Prüfen Sie die lauschenden Sockets:

```bash
sudo ss -lntp | grep -E ':5050|:5000'
```

Nur die lokale Anwendungsbindung auf localhost sollte vorhanden sein.

---

# 23. Den Secret-Mount prüfen

Bestätigen Sie, dass das Secret gemountet ist:

```bash
sudo docker inspect lums \
    --format='{{range .Mounts}}{{println .Source "->" .Destination "RW=" .RW}}{{end}}'
```

Das Anwendungssecret sollte ähnlich erscheinen wie:

```text
/etc/lums/secrets/lums_secret -> /run/secrets/lums_secret RW=false
```

Die genaue Ausgabe kann zusätzliche Mount-Informationen enthalten.

Die wichtige Eigenschaft ist:

```text
RW=false
```

Geben Sie niemals den Inhalt des Secrets aus.

Ein direkter Lesbarkeitstest ist ausreichend:

```bash
sudo docker exec lums \
    sh -c 'test -r /run/secrets/lums_secret && echo "secret mount: OK"'
```

Erwartet:

```text
secret mount: OK
```

---

# 24. Den persistenten Volume-Mount prüfen

Inspizieren Sie die Container-Mounts:

```bash
sudo docker inspect lums \
    --format='{{range .Mounts}}{{println .Type .Source "->" .Destination "RW=" .RW}}{{end}}'
```

Das LUMS-Daten-Volume muss gemountet sein unter:

```text
/var/lib/lums
```

und muss beschreibbar sein:

```text
RW=true
```

Die erwartete Beziehung ist:

```text
lums-data
    ↓
/var/lib/lums
```

Das Root-Dateisystem bleibt schreibgeschützt, während das dedizierte Daten-Volume den erforderlichen persistenten Schreibzugriff bereitstellt.

---

# 25. Das schreibgeschützte Root-Dateisystem prüfen

Das Anwendungs-Root-Dateisystem muss schreibgeschützt sein.

Die Container-Laufzeit sollte melden:

```text
ReadonlyRootfs=true
```

Ein kontrollierter Schreibtest kann innerhalb des Containers durchgeführt werden.

Zum Beispiel:

```bash
sudo docker exec lums \
    sh -c 'touch /app/.write-test'
```

Der Befehl sollte fehlschlagen, weil `/app` Teil des schreibgeschützten Container-Dateisystems ist.

Deaktivieren Sie das schreibgeschützte Root-Dateisystem nicht nur deshalb, weil eine Anwendungskomponente versucht, außerhalb ihrer vorgesehenen beschreibbaren Speicherorte zu schreiben.

Wenn die Anwendung persistente Daten benötigt, verwenden Sie das entsprechende Volume oder ein Laufzeit-Dateisystem.

---

# 26. Das beschreibbare temporäre Dateisystem prüfen

Der Container stellt ein dediziertes `/tmp`-tmpfs bereit.

Prüfen Sie:

```bash
sudo docker exec lums \
    sh -c 'touch /tmp/lums-write-test && rm -f /tmp/lums-write-test && echo "tmpfs: OK"'
```

Erwartet:

```text
tmpfs: OK
```

Das temporäre Dateisystem ist konfiguriert mit:

```text
noexec
nosuid
```

und einem Größenlimit.

Dies bietet temporären beschreibbaren Speicher, ohne das Container-Root-Dateisystem beschreibbar zu machen.

---

# 27. Das Anwendungsdatenverzeichnis prüfen

Die LUMS-Anwendung benötigt Schreibzugriff auf ihr persistentes Datenverzeichnis.

Test:

```bash
sudo docker exec lums \
    sh -c 'touch /var/lib/lums/.write-test && rm -f /var/lib/lums/.write-test && echo "data volume: OK"'
```

Erwartet:

```text
data volume: OK
```

Dies bestätigt, dass das dedizierte beschreibbare Volume verfügbar ist, während der Rest des Containers schreibgeschützt bleibt.

---

# 28. Den Anwendungsbenutzer prüfen

Bestätigen Sie den effektiven Laufzeitbenutzer:

```bash
sudo docker exec lums \
    id
```

Der Prozess sollte als unprivilegierter LUMS-Benutzer laufen.

Die erwartete Identität enthält:

```text
uid=10001(lums)
```

Die genauen Gruppeninformationen können je nach Image-Konfiguration variieren.

Der Container darf während des normalen Betriebs nicht als:

```text
root
```

laufen.

---

# 29. Datenbankinitialisierung

Nachdem der Container gestartet ist, prüfen Sie, ob die Datenbank existiert:

```bash
sudo docker exec lums \
    ls -lh /var/lib/lums/lums.db
```

Wenn die Anwendung erfolgreich initialisiert wurde, sollte die Datenbank vorhanden sein.

Die Datenbank befindet sich unter:

```text
/var/lib/lums/lums.db
```

innerhalb des Containers und persistiert physisch über:

```text
lums-data
```

Die Datenbank darf nicht kopiert werden nach:

```text
/opt/lums-public
```

oder in Git committet werden.

---

# 30. SQLite-Laufzeitkonfiguration prüfen

Die aktuelle LUMS-Produktionsbasis verwendet:

```text
journal_mode = wal
busy_timeout = 5000 ms
synchronous = 2
foreign_keys = ON
```

Die Anwendung aktiviert ausdrücklich die Fremdschlüssel-Durchsetzung für Datenbankverbindungen.

Die Datenbank verwendet WAL-Modus für den normalen Produktionsbetrieb.

Die Laufzeitkonfiguration kann aus der Anwendungsdatenbank inspiziert werden.

Zum Beispiel:

```bash
sudo docker exec -i lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

for pragma in (
    "journal_mode",
    "busy_timeout",
    "synchronous",
    "foreign_keys",
):
    print(f"{pragma}={db.execute(f'PRAGMA {pragma}').fetchone()[0]}")

db.close()
PY
```

Erwartete Werte sind äquivalent zu:

```text
journal_mode=wal
busy_timeout=5000
synchronous=2
foreign_keys=0
```

Die Anwendung aktiviert Fremdschlüssel ausdrücklich.

---

# 31. Datenbankintegrität prüfen

Führen Sie eine SQLite-Integritätsprüfung aus:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
result = db.execute("PRAGMA integrity_check").fetchone()[0]
print(result)
db.close()
PY
```

Erwartet:

```text
ok
```

Fahren Sie nicht mit der Bereitstellung fort, wenn die Integritätsprüfung eine Datenbankbeschädigung meldet.

---

# 32. Datenbankmigrationen prüfen

LUMS verwendet Anwendungsmigrationen für Datenbankschemaänderungen.

Inspizieren Sie die migrationsbezogenen Dateien:

```bash
ls -lh \
    server/*migration*.py
```

Die Anwendung führt erforderliche Migrationen während des Starts/der Bereitstellung gemäß der aktuellen Implementierung aus.

Inspizieren Sie nach dem Start die Anwendungslogs:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Migrationsfehler müssen untersucht werden, bevor Benutzer erstellt oder Clients verbunden werden.

Ändern Sie das Produktions-SQLite-Schema nicht manuell, es sei denn, die Projektdokumentation verlangt dies ausdrücklich.

---

# 33. Lokale Anwendungsvalidierung

Bevor Sie Nginx konfigurieren, bestätigen Sie, dass die Anwendung lokal antwortet.

Die Docker-Anwendung ist gebunden an:

```text
127.0.0.1:5050
```

Eine lokale Anfrage kann getestet werden mit:

```bash
curl -I \
    http://127.0.0.1:5050/
```

Die genaue HTTP-Antwort hängt von der aktuellen Anwendungsroute und dem Authentifizierungszustand ab.

Die wichtige Anforderung ist, dass die Anfrage die laufende LUMS-Anwendung erreicht.

Wenn die Verbindung fehlschlägt, inspizieren Sie:

```bash
sudo docker ps \
    --filter name=lums
```

und:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Setzen Sie Port `5050` nicht als Fehlerbehebungsworkaround extern aus.

---

# 34. Erster Server-Checkpoint

Zu diesem Zeitpunkt sollte der Server erfüllen:

```text
[ ] Repository cloned
[ ] Working tree reviewed
[ ] Production tests completed
[ ] Docker image built
[ ] Persistent lums-data volume exists
[ ] Hardened container running
[ ] Container runs as lums
[ ] Root filesystem is read-only
[ ] All capabilities are dropped
[ ] no-new-privileges is enabled
[ ] Privileged mode is disabled
[ ] Secret is mounted read-only
[ ] Persistent data volume is mounted
[ ] Port 5050 is localhost-only
[ ] SQLite database exists
[ ] SQLite integrity check succeeds
[ ] Foreign keys are enabled
[ ] Local application endpoint responds
```

Verbinden Sie noch keine Produktionsclients.

Der nächste Abschnitt konfiguriert Nginx, HTTPS und den externen LUMS-Endpunkt.

# 35. Nginx konfigurieren

Nginx stellt den externen HTTPS-Einstiegspunkt für LUMS bereit.

Die Anwendung selbst bleibt gebunden an:

```text
127.0.0.1:5050
```

Der vorgesehene Anfragepfad ist:

```text
Client
   │
   │ HTTPS
   ▼
Nginx :443
   │
   │ HTTP localhost
   ▼
127.0.0.1:5050
   │
   ▼
LUMS container :5000
```

Erstellen Sie die Nginx-Site-Konfiguration:

```bash
sudo tee /etc/nginx/sites-available/lums > /dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;

    server_name LUMS-SERVER;

    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;

    server_name LUMS-SERVER;

    ssl_certificate     /etc/lums/tls/lums.crt;
    ssl_certificate_key /etc/lums/tls/lums.key;

    location / {
        proxy_pass http://127.0.0.1:5050;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

Ersetzen Sie:

```text
LUMS-SERVER
```

durch den Hostnamen oder die Adresse, die von der Installation verwendet wird.

Verwenden Sie den literalen Platzhalter nicht in einer Produktionskonfiguration.

---

# 36. Die LUMS-Nginx-Konfiguration aktivieren

Erstellen Sie den Enabled-Site-Link:

```bash
sudo ln -s \
    /etc/nginx/sites-available/lums \
    /etc/nginx/sites-enabled/lums
```

Wenn die Standard-Nginx-Site nicht benötigt wird, entfernen Sie sie:

```bash
sudo rm -f \
    /etc/nginx/sites-enabled/default
```

Entfernen Sie keine anderen Nginx-Konfigurationen, die zu nicht zusammenhängenden Anwendungen gehören.

---

# 37. Die Nginx-Konfiguration validieren

Testen Sie die Konfiguration immer, bevor Sie Nginx neu laden:

```bash
sudo nginx -t
```

Erwartet:

```text
syntax is ok
test is successful
```

Erst nach einem erfolgreichen Konfigurationstest sollte Nginx neu geladen werden:

```bash
sudo systemctl reload nginx
```

Prüfen Sie den Dienst:

```bash
sudo systemctl status \
    nginx \
    --no-pager
```

Nginx muss laufen, bevor Sie mit der HTTPS-Validierung fortfahren.

---

# 38. TLS-Zertifikatsdateien prüfen

Bestätigen Sie, dass die konfigurierten Zertifikatsdateien existieren:

```bash
sudo ls -lh \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

Prüfen Sie die Berechtigungen:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

Der private Schlüssel sollte normalerweise sein:

```text
600
```

Das Zertifikat kann normalerweise sein:

```text
644
```

Geben Sie niemals den Inhalt des privaten Schlüssels aus.

---

# 39. Den HTTPS-Endpunkt prüfen

Testen Sie HTTPS lokal:

```bash
curl -I \
    https://LUMS-SERVER/
```

Ersetzen Sie `LUMS-SERVER` durch den Hostnamen, der vom TLS-Zertifikat des Servers abgedeckt ist. Verwenden Sie `-k` nicht für routinemäßige Verifikation; es überspringt die Zertifikatsvalidierung.

Wenn das Zertifikat vom System als vertrauenswürdig eingestuft wird, verwenden Sie die Zertifikatsverifikation:

```bash
curl -I \
    https://LUMS-SERVER/
```

Eine erfolgreiche Antwort bestätigt, dass die Anfrage den Nginx-HTTPS-Endpunkt erreicht.

Der genaue HTTP-Status hängt von der angeforderten Route und dem Authentifizierungszustand ab.

Die wichtige Anforderung ist, dass die TLS-Verbindung erfolgreich ist und die Anfrage LUMS erreicht.

---

# 40. HTTP-nach-HTTPS-Weiterleitung prüfen

Der HTTP-Listener muss Clients auf HTTPS weiterleiten.

Test:

```bash
curl -I \
    http://LUMS-SERVER/
```

Erwartetes Verhalten:

```text
HTTP/1.1 301 ...
Location: https://...
```

Die LUMS-Anwendung sollte nicht über eine unverschlüsselte HTTP-Verbindung betrieben werden.

Konfigurieren Sie Clients nicht dauerhaft mit deaktivierter Zertifikatsverifikation, nur weil das anfängliche Zertifikat nicht vertrauenswürdig ist.

Beheben Sie stattdessen die Trust-Konfiguration.

---

# 41. Den externen Netzwerkpfad prüfen

Inspizieren Sie die lauschenden Sockets:

```bash
sudo ss -lntp | grep -E ':80|:443|:5050|:5000'
```

Die vorgesehene Architektur ist:

```text
80
 │
 └── HTTP redirect
        │
        ▼
443
 │
 └── Nginx
        │
        ▼
127.0.0.1:5050
        │
        ▼
Docker :5000
```

Port `5050` darf nicht dem LAN ausgesetzt sein.

Port `5000` darf nicht direkt ausgesetzt sein.

Der Docker-Anwendungsport ist ein interner Reverse-Proxy-Endpunkt.

---

# 42. Sicherheitsheader prüfen

Inspizieren Sie die HTTPS-Antwortheader:

```bash
curl -I \
    https://LUMS-SERVER/
```

Überprüfen Sie die zurückgegebenen Header, anstatt anzunehmen, dass die Sicherheitskonfiguration aktiv ist.

Relevante Sicherheitsheader können umfassen:

```text
X-Content-Type-Options
X-Frame-Options
Referrer-Policy
Content-Security-Policy
```

Die genauen Header hängen von der aktuellen LUMS-Anwendung und der Nginx-Konfiguration ab.

Wenn ein erforderlicher Header fehlt, inspizieren Sie die effektive Nginx-Konfiguration:

```bash
sudo nginx -T
```

und die Anwendungskonfiguration:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Fügen Sie Sicherheitsheader nicht blind hinzu, ohne zu prüfen, welche Schicht bereits dafür verantwortlich ist.

---

# 43. Host-Verarbeitung prüfen

Die Produktionsbereitstellung sollte die Anwendung nicht über eine unbeabsichtigte Standard-Nginx-Site aussetzen.

Überprüfen Sie die aktive Konfiguration:

```bash
sudo nginx -T
```

Prüfen Sie die aktivierten Sites:

```bash
ls -la \
    /etc/nginx/sites-enabled/
```

Der vorgesehene LUMS-Virtual-Host sollte vorhanden sein.

Die Standard-Site sollte nicht unerwartet die LUMS-Anwendung ausliefern.

Wenn eine IP-Adresse als LUMS-Endpunkt verwendet wird, stellen Sie sicher, dass der konfigurierte `server_name` und das Zertifikat zum tatsächlichen Bereitstellungsmodell passen.

---

# 44. Docker-Exposition erneut prüfen

Nachdem Nginx konfiguriert ist, bestätigen Sie, dass die Anwendung weiterhin nur auf localhost beschränkt ist:

```bash
sudo docker port lums
```

Erwartet:

```text
5000/tcp -> 127.0.0.1:5050
```

Der Reverse-Proxy erfordert keine Änderung der Docker-Bindung.

Ändern Sie sie nicht auf:

```text
0.0.0.0:5050
```

nur weil Nginx im Netzwerk lauscht.

Nginx und Docker haben absichtlich getrennte Expositionsgrenzen.

---

# 45. Den initialen Administrator erstellen

Der initiale Administrator muss über den Administrator-Initialisierungsmechanismus des aktuellen Repositorys erstellt werden.

Bevor Sie einen Initialisierungsbefehl ausführen, inspizieren Sie die verfügbare Repository-Implementierung:

```bash
cd /opt/lums-public
```

Überprüfen Sie die sicherheitsbezogenen Initialisierungsdateien:

```bash
find server \
    -maxdepth 1 \
    -type f \
    -iname '*security*' \
    -o -iname '*migration*'
```

Inspizieren Sie dann die aktuelle Migrations-/Initialisierungsimplementierung, bevor Sie sie ausführen.

Zum Beispiel:

```bash
sed -n '1,260p' \
    server/security_migration.py
```

Verwenden Sie das Initialisierungsverfahren, das von der exakten Repository-Revision bereitgestellt wird, die bereitgestellt wird.

> [!IMPORTANT]
> Kopieren Sie kein Administratorpasswort in die Shell-Historie oder Dokumentation.

Der initiale Administrator muss erhalten:

```text
role = administrator
```

Das Administratorkonto ist für den ersten Web-Login und die anschließende Client-Administration erforderlich.

---

# 46. Das Administratorkonto prüfen

Nach der Administratorinitialisierung prüfen Sie das Konto, ohne Authentifizierungsmaterial offenzulegen.

Eine Datenbankinspektion kann aus dem Container heraus durchgeführt werden:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

rows = db.execute(
    """
    SELECT id, username, enabled, role
    FROM users
    ORDER BY id
    """
).fetchall()

for row in rows:
    print(row)

db.close()
PY
```

Erwartete Administrator-Eigenschaften umfassen:

```text
enabled = 1
role = administrator
```

Geben Sie nicht aus:

```text
password hashes
session data
client tokens
application secrets
```

---

# 47. Administratorpasswort

Verwenden Sie ein eindeutiges Administratorpasswort.

Das Passwort sollte nicht wiederverwendet werden von:

```text
other servers
Linux accounts
GitHub accounts
email accounts
network devices
other LUMS installations
```

Die LUMS-Anwendung speichert Passwörter mit dem konfigurierten Passwort-Hashing-Mechanismus.

Versuchen Sie nicht, den Anwendungspasswort-Hash manuell in SQLite zu ersetzen.

Wenn das Administratorpasswort geändert werden muss, verwenden Sie den unterstützten Anwendungsmechanismus.

---

# 48. Erster Web-Login

Öffnen Sie den LUMS-HTTPS-Endpunkt:

```text
https://LUMS-SERVER/
```

Melden Sie sich mit dem Administratorkonto an.

Nach der Authentifizierung sollte der Administrator Zugriff auf die administrative Oberfläche haben.

Die Administratoroberfläche sollte Zugriff auf die Bereiche bieten, die von der aktuellen RBAC-Implementierung erlaubt sind.

Mindestens sollte der Administrator auf Folgendes zugreifen können:

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
User management
```

---

# 49. Administrator-RBAC prüfen

Prüfen Sie nach dem Login, dass administrative Funktionen verfügbar sind.

Der Administrator sollte auf die Benutzerverwaltung zugreifen können.

Der Administrator sollte außerdem Client-Management-Operationen durchführen können, die von der aktuellen Implementierung erlaubt sind.

Serverseitige Autorisierung bleibt die Sicherheitsgrenze.

Die Browseroberfläche ist nicht vertrauenswürdig, nur weil ein Element sichtbar oder ausgeblendet ist.

---

# 50. Einen Operator erstellen

Nachdem das Administratorkonto geprüft wurde, erstellen Sie ein Operatorkonto über die LUMS-Benutzerverwaltungsoberfläche.

Die Operatorrolle ist für operatives Update-Management vorgesehen.

Ein Operator kann zugreifen auf:

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
```

Ein Operator darf keine ausschließlich für Administratoren vorgesehenen Funktionen durchführen wie:

```text
User management
Role management
Client creation/disabling
Client-token rotation
```

Prüfen Sie die Berechtigungen über die Anwendungsoberfläche und, wo angebracht, das API-Autorisierungsverhalten.

---

# 51. Einen Viewer erstellen

Ein Viewer-Konto kann erstellt werden, wenn schreibgeschützter Zugriff erforderlich ist.

Die Viewerrolle ist absichtlich eingeschränkt.

Ein Viewer kann zugreifen auf:

```text
Clients
Installed software
```

Die folgenden Bereiche dürfen für einen Viewer nicht verfügbar sein:

```text
Available updates
Update jobs
Update history
Package management
System maintenance
```

Diese Einschränkungen werden serverseitig durchgesetzt.

Die Oberfläche kann nicht verfügbare Funktionen zusätzlich ausblenden.

---

# 52. Viewer-Isolation prüfen

Melden Sie sich mit einem Viewer-Konto an und prüfen Sie die sichtbare Oberfläche.

Der Viewer sollte keine Management-Steuerelemente erhalten.

Der Viewer darf die UI nicht umgehen und geschützte Endpunkte direkt aufrufen können.

Für geschützte Operationen sollte ein Autorisierungsfehler zurückgegeben werden.

Das erwartete Prinzip ist:

```text
UI restriction
     +
server-side authorization
     =
RBAC boundary
```

Verlassen Sie sich niemals auf JavaScript oder ausgeblendete HTML-Elemente als einziges Autorisierungsmechanismus.

---

# 53. Sitzungs- und CSRF-Schutz prüfen

Prüfen Sie nach dem ersten erfolgreichen Login, dass die Anwendung ihre konfigurierten Sitzungs- und CSRF-Schutzmechanismen verwendet.

Die Installation sollte den CSRF-Schutz nicht deaktivieren, damit API-Anfragen oder Browseraktionen funktionieren.

Wenn eine legitime Anfrage mit einem CSRF-Fehler fehlschlägt, inspizieren Sie den Anwendungsfluss, anstatt den Schutz zu deaktivieren.

Sitzungsbezogenes Verhalten ist dokumentiert in:

```text
docs/security.md
```

---

# 54. Login-Ratenbegrenzung prüfen

Der aktuelle Loginschutz verwendet persistente Fehlerverfolgung.

Die konfigurierte Progression ist:

```text
5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

Eine erfolgreiche Authentifizierung löscht den zutreffenden Fehlerzustand.

Lösen Sie nicht wiederholt fehlgeschlagene Authentifizierungen gegen eine Produktionsinstallation aus, nur um den Mechanismus zu testen.

Verwenden Sie die vorhandene Testsuite für wiederholte automatisierte Validierung.

---

# 55. Server-Validierungs-Checkpoint

Zu diesem Zeitpunkt prüfen Sie:

```text
[ ] Nginx is running
[ ] Nginx configuration passes nginx -t
[ ] TLS certificate is installed
[ ] TLS private key is protected
[ ] HTTPS works
[ ] HTTP redirects to HTTPS
[ ] Docker remains localhost-only
[ ] Port 5000 is not externally exposed
[ ] Security headers are present as configured
[ ] Default Nginx site is not unintentionally serving LUMS
[ ] Administrator account exists
[ ] Administrator can log in
[ ] Administrator RBAC works
[ ] Operator role can be created
[ ] Viewer role can be created
[ ] Viewer restrictions are enforced server-side
[ ] CSRF protection remains enabled
[ ] Session protection remains enabled
```

Erst nachdem der Server diese Prüfungen bestanden hat, sollten Linux-Clients installiert werden.

Der nächste Abschnitt behandelt den Linux-Agent, die Client-Konfiguration, TLS-Vertrauen und systemd-Integration.

# 56. Linux-Client-Installation

LUMS-Clients sind Linux-Systeme, die vom LUMS-Server verwaltet werden.

Eine Client-Installation besteht aus:

```text
Linux system
    ↓
LUMS Agent
    ↓
Client configuration
    ↓
Client token
    ↓
TLS trust
    ↓
systemd service
    ↓
Reporting timer
```

Die Update-Ausführung wird separat durch den Execution Watcher behandelt.

Die aktuelle Agent-Version ist:

```text
1.7.0
```

Die aktuelle Watcher-Version ist:

```text
1.2.1
```

---

# 57. Unterstützte Linux-Clients

Die aktuellen Paketverwaltungsimplementierungen unterstützen:

```text
Debian / Ubuntu
    ↓
APT / dpkg

Arch Linux
    ↓
pacman
```

Prüfen Sie das Betriebssystem, bevor Sie den Client installieren:

```bash
cat /etc/os-release
```

Prüfen Sie die Architektur:

```bash
uname -m
```

Prüfen Sie systemd:

```bash
systemctl --version
```

Der Client erfordert eine funktionierende systemd-Installation.

---

# 58. Client-Netzwerkanforderungen

Der Client muss den LUMS-HTTPS-Endpunkt erreichen können.

Testen Sie die grundlegende Netzwerkkonnektivität:

```bash
ping LUMS-SERVER
```

Ein erfolgreicher Ping ist nicht erforderlich, wenn ICMP blockiert wird.

Die wichtige Anforderung ist HTTPS-Konnektivität.

Testen Sie den LUMS-Endpunkt:

```bash
curl -I \
    https://LUMS-SERVER/
```

Wenn der Server eine private CA verwendet, muss der Client dieser CA vertrauen, bevor er fortfährt.

Deaktivieren Sie die TLS-Verifikation nicht als dauerhaften Workaround.

---

# 59. Den LUMS Agent beschaffen

Der Agent-Quellcode ist im LUMS-Repository enthalten.

Beschaffen Sie auf dem Client das Repository oder übertragen Sie die erforderlichen Agent-Dateien über die genehmigte Bereitstellungsmethode.

Die relevanten Dateien sind:

```text
agent/agent.py
agent/watcher.py
agent/package_manager.py
```

Das empfohlene Installationsverzeichnis ist:

```text
/opt/lums-agent
```

Erstellen Sie es:

```bash
sudo install -d -m 755 \
    /opt/lums-agent
```

---

# 60. Die Agent-Dateien installieren

Aus dem LUMS-Repository:

```bash
cd /opt/lums-public
```

Installieren Sie den Agent:

```bash
sudo cp \
    agent/agent.py \
    /opt/lums-agent/agent.py
```

Installieren Sie den Watcher:

```bash
sudo cp \
    agent/watcher.py \
    /opt/lums-agent/watcher.py
```

Installieren Sie die Paketmanager-Abstraktion:

```bash
sudo cp \
    agent/package_manager.py \
    /opt/lums-agent/package_manager.py
```

Prüfen Sie:

```bash
ls -lh \
    /opt/lums-agent/
```

Das Verzeichnis sollte die installierten Agent-Komponenten enthalten.

---

# 61. Agent-Versionen prüfen

Prüfen Sie die installierte Agent-Version:

```bash
grep -n \
    'AGENT_VERSION' \
    /opt/lums-agent/agent.py
```

Die aktuelle Version ist:

```text
1.7.0
```

Prüfen Sie den Watcher:

```bash
grep -n \
    'WATCHER_VERSION' \
    /opt/lums-agent/watcher.py
```

Die aktuelle Version ist:

```text
1.2.1
```

Wenn die installierten Versionen nicht zur vorgesehenen Bereitstellungsrevision passen, stoppen Sie und prüfen Sie, ob die korrekte Repository-Revision verwendet wird.

---

# 62. systemd-Service-Dateien installieren

Agent und Watcher verwenden separate systemd-Dienste.

Installieren Sie den Agent-Dienst:

```bash
sudo cp \
    agent/lums-agent.service \
    /etc/systemd/system/lums-agent.service
```

Installieren Sie den Watcher-Dienst:

```bash
sudo cp \
    agent/lums-agent-watcher.service \
    /etc/systemd/system/lums-agent-watcher.service
```

Installieren Sie den Reporting-Timer:

```bash
sudo cp \
    agent/lums-agent.timer \
    /etc/systemd/system/lums-agent.timer
```

Installieren Sie den Watcher-Timer:

```bash
sudo cp \
    agent/lums-agent-watcher.timer \
    /etc/systemd/system/lums-agent-watcher.timer
```

Laden Sie systemd neu:

```bash
sudo systemctl daemon-reload
```

---

# 63. Die systemd-Units prüfen

Inspizieren Sie den Agent-Dienst:

```bash
systemctl cat \
    lums-agent.service
```

Inspizieren Sie den Watcher-Dienst:

```bash
systemctl cat \
    lums-agent-watcher.service
```

Inspizieren Sie den Agent-Timer:

```bash
systemctl cat \
    lums-agent.timer
```

Inspizieren Sie den Watcher-Timer:

```bash
systemctl cat \
    lums-agent-watcher.timer
```

Die Units sollten auf die installierten Dateien unter:

```text
/opt/lums-agent/
```

verweisen.

Aktivieren Sie die Timer nicht, bis die Client-Konfiguration und Authentifizierung abgeschlossen sind.

---

# 64. Die Client-Konfiguration erstellen

Die Client-Konfiguration wird außerhalb des Git-Repositories gespeichert.

Verwenden Sie:

```text
/etc/default/lums-agent
```

Erstellen Sie die Datei:

```bash
sudo install -m 600 /dev/null \
    /etc/default/lums-agent
```

Die Konfiguration enthält den LUMS-Serverendpunkt und den Client-Token.

Beispielstruktur:

```text
LUMS_BASE=https://LUMS-SERVER
LUMS_TOKEN=<CLIENT-TOKEN>
```

Ersetzen Sie:

```text
LUMS-SERVER
```

durch den tatsächlichen LUMS-Serverendpunkt.

Ersetzen Sie:

```text
<CLIENT-TOKEN>
```

durch den Token, der diesem Client zugewiesen ist.

Schützen Sie die Konfiguration:

```bash
sudo chmod 600 \
    /etc/default/lums-agent
```

Prüfen Sie, ohne den Inhalt anzuzeigen:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/default/lums-agent
```

Erwartet:

```text
600
```

---

# 65. Client-Tokens

Jeder LUMS-Client hat seinen eigenen Authentifizierungstoken.

Der Token wird verwendet als:

```text
Authorization: Bearer <CLIENT-TOKEN>
```

Der Server benötigt nach der Bereitstellung nicht den ursprünglichen Tokenwert.

Der Server speichert eine kryptografische Repräsentation des Tokens zur Validierung.

Das bedeutet, dass Client-Anmeldeinformationen wie Passwörter behandelt werden sollten.

Legen Sie niemals einen echten Token ab in:

```text
Git
documentation
screenshots
issue reports
shell history
public configuration
```

---

# 66. Den Client-Token bereitstellen

Erstellen oder stellen Sie den Client über die LUMS-Administratoroberfläche gemäß dem aktuellen Client-Management-Workflow bereit.

Der resultierende Client-Token muss über einen sicheren Kanal an den vorgesehenen Client übertragen werden.

Speichern Sie ihn nur in:

```text
/etc/default/lums-agent
```

auf dem Client.

Verwenden Sie einen Client-Token nicht für mehrere Maschinen.

Die vorgesehene Beziehung ist:

```text
Client A
    ↓
Token A

Client B
    ↓
Token B

Client C
    ↓
Token C
```

Ein kompromittierter Token sollte daher nur den zugehörigen Client identifizieren.

---

# 67. Client-Token-Rotation

Client-Tokens können von einem Administrator rotiert werden.

Der Rotationsablauf ist:

```text
Current token
     ↓
Administrator rotates token
     ↓
Old token invalidated
     ↓
New token issued
     ↓
Client configuration updated
```

Nach der Aktualisierung der Client-Konfiguration führen Sie den Agent manuell aus, um zu prüfen, dass die Authentifizierung erfolgreich ist.

Ein rotierter Token darf nicht unbegrenzt weiter akzeptiert werden.

---

# 68. TLS-Vertrauen

Der LUMS Agent kommuniziert über HTTPS mit dem Server.

Die Zertifikatsverifikation muss aktiviert bleiben.

Für ein öffentlich vertrauenswürdiges Zertifikat ist der normale Trust Store des Betriebssystems ausreichend.

Für eine private Labor-CA installieren Sie das CA-Zertifikat auf dem Client.

Lösen Sie Zertifikatsprobleme nicht durch Deaktivieren der Verifikation.

Die korrekte Lösung besteht darin, den Client dazu zu bringen, der vorgesehenen Zertifizierungsstelle zu vertrauen.

---

# 69. TLS-Vertrauen unter Debian / Ubuntu

Auf Debian-Familien-Systemen kann eine private CA in den System-Trust-Store installiert werden.

Kopieren Sie das CA-Zertifikat:

```bash
sudo cp \
    lums-ca.crt \
    /usr/local/share/ca-certificates/lums-ca.crt
```

Aktualisieren Sie den Trust Store:

```bash
sudo update-ca-certificates
```

Prüfen Sie, dass das Zertifikat akzeptiert wird:

```bash
curl -I \
    https://LUMS-SERVER/
```

Wenn der Befehl ohne `-k` erfolgreich ist, funktioniert die System-Trust-Konfiguration.

---

# 70. TLS-Vertrauen unter Arch Linux

Installieren Sie auf Arch Linux die private CA mit dem konfigurierten Trust-Store-Mechanismus des Systems.

Aktualisieren Sie nach der Installation der CA die Trust-Datenbank gemäß der aktiven Trust-Store-Konfiguration.

Prüfen Sie:

```bash
curl -I \
    https://LUMS-SERVER/
```

Die Verbindung sollte erfolgreich sein ohne:

```text
-k
```

Konfigurieren Sie den Agent nicht dauerhaft so, dass er die Zertifikatsverifikation ignoriert.

---

# 71. Den Paketmanager prüfen

Der Agent erkennt die unterstützte Paketverwaltungsfamilie.

Für Debian/Ubuntu:

```bash
command -v apt
```

und:

```bash
command -v dpkg-query
```

Prüfen Sie installierte Pakete:

```bash
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n' \
    | head
```

Prüfen Sie verfügbare Updates:

```bash
apt list --upgradable
```

Für Arch Linux:

```bash
command -v pacman
```

Prüfen Sie installierte Pakete:

```bash
pacman -Q | head
```

Prüfen Sie verfügbare Updates:

```bash
pacman -Qu
```

Die Paketmanager-Abstraktion verwendet automatisch die entsprechende Implementierung.

---

# 72. Agent-Berechtigungen prüfen

Inspizieren Sie das Installationsverzeichnis:

```bash
ls -ld \
    /opt/lums-agent
```

Inspizieren Sie die installierten Dateien:

```bash
ls -lh \
    /opt/lums-agent/
```

Der Agent benötigt keinen Schreibzugriff auf sein eigenes Quellverzeichnis.

Die Client-Konfiguration bleibt separat geschützt:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/default/lums-agent
```

Erwartet:

```text
600
```

Der Agent benötigt ausreichende Systemprivilegien, um den Paketzustand zu inspizieren und Paketoperationen durchzuführen.

Die genauen Laufzeitprivilegien werden durch den installierten systemd-Dienst definiert.

---

# 73. Die Agent-Konfiguration prüfen

Bevor Sie den Dienst starten, prüfen Sie, dass die Konfigurationsdatei existiert:

```bash
sudo test -r \
    /etc/default/lums-agent \
    && echo "agent configuration: OK"
```

Geben Sie den Inhalt der Konfigurationsdatei nicht aus.

Prüfen Sie, dass die erforderlichen Variablen existieren, ohne den Token offenzulegen:

```bash
sudo sh -c '
set -a
. /etc/default/lums-agent
set +a

test -n "$LUMS_BASE" &&
echo "LUMS_BASE: configured"

test -n "$LUMS_TOKEN" &&
echo "LUMS_TOKEN: configured"
'
```

Der Tokenwert selbst darf nicht ausgegeben werden.

---

# 74. Den Agent manuell testen

Bevor Sie den Timer aktivieren, führen Sie den Agent einmal manuell aus:

```bash
sudo systemctl start \
    lums-agent.service
```

Prüfen Sie das Ergebnis:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Der Agent ist ein One-Shot-Dienst.

Nach erfolgreichem Abschluss kann er anzeigen:

```text
Active: inactive (dead)
```

Dies ist normal.

Das wichtige Ergebnis ist:

```text
status=0/SUCCESS
```

Inspizieren Sie das Journal:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

---

# 75. Den ersten Client-Bericht prüfen

Ein erfolgreicher Agent-Lauf sollte den Client beim LUMS-Server melden.

Der vollständige Pfad ist:

```text
Agent
   ↓
HTTPS
   ↓
Nginx
   ↓
LUMS API
   ↓
Bearer authentication
   ↓
Client lookup
   ↓
Report accepted
```

Inspizieren Sie bei Bedarf die Serverlogs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Der Client sollte nach einem erfolgreichen Bericht in der LUMS-Weboberfläche erscheinen.

Der lokale Dienst erfolgreich zu sein ist allein nicht ausreichend.

Der Server muss den Bericht akzeptieren.

---

# 76. Den Client in der Weboberfläche prüfen

Melden Sie sich als Administrator oder Operator an.

Öffnen Sie die Client-Übersicht.

Der neue Client sollte Informationen melden wie:

```text
Hostname
IP address
Operating system
Architecture
Agent version
Last report
Installed packages
Available updates
```

Die gemeldeten Informationen gehören zu diesem Client.

Ein Client darf nicht auf Ressourcen eines anderen Clients zugreifen.

---

# 77. Den Reporting-Timer aktivieren

Erst nachdem der manuelle Agent-Lauf erfolgreich war, sollte der Reporting-Timer aktiviert werden:

```bash
sudo systemctl enable --now \
    lums-agent.timer
```

Prüfen Sie:

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

Inspizieren Sie den Zeitplan:

```bash
systemctl list-timers \
    lums-agent.timer \
    --no-pager
```

Der Timer startet regelmäßig:

```text
lums-agent.service
```

Der Dienst selbst bleibt eine One-Shot-Unit.

Daher ist es normal, dass der Dienst zwischen Timer-Ausführungen zurückkehrt zu:

```text
inactive (dead)
```

---

# 78. Geplante Berichterstattung prüfen

Nach dem Aktivieren des Timers inspizieren Sie die nächste geplante Ausführung:

```bash
systemctl list-timers \
    --all \
    --no-pager | grep lums-agent
```

Nachdem der Timer ausgeführt wurde, inspizieren Sie:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Prüfen Sie den entsprechenden Client-Bericht in LUMS.

Ein gesunder Reporting-Zyklus ist:

```text
Timer
  ↓
Agent service
  ↓
System inventory
  ↓
Package inventory
  ↓
Update detection
  ↓
HTTPS report
  ↓
LUMS database
```

---

# 79. Client-Installations-Checkpoint

Bevor Sie den Execution Watcher installieren, prüfen Sie:

```text
[ ] Supported Linux distribution
[ ] Python 3 available
[ ] systemd available
[ ] Package manager available
[ ] Agent installed
[ ] Agent version verified
[ ] Watcher files installed
[ ] Client configuration exists
[ ] Client token protected
[ ] TLS certificate trusted
[ ] Agent service succeeds
[ ] Client report accepted
[ ] Client visible in LUMS
[ ] Reporting timer enabled
[ ] Scheduled reporting verified
```

Fahren Sie nicht mit Update-Job-Tests fort, bis der Reporting-Pfad funktioniert.

Der nächste Abschnitt installiert und validiert den Execution Watcher.

# 80. Den Execution Watcher installieren

Der LUMS Execution Watcher ist verantwortlich für das Erkennen und Ausführen ausstehender Update-Jobs auf dem Client.

Die Architektur trennt Berichterstattung von Ausführung:

```text
Reporting
    │
    ▼
lums-agent.service
    │
    └── system inventory / update detection

Execution
    │
    ▼
lums-agent-watcher.service
    │
    └── pending update jobs
```

Diese Trennung ermöglicht es der regulären Client-Berichterstattung, unabhängig von der Update-Ausführung weiterzulaufen.

---

# 81. Die Watcher-Installation prüfen

Prüfen Sie, dass der Watcher vorhanden ist:

```bash
ls -lh \
    /opt/lums-agent/watcher.py
```

Prüfen Sie die installierte Version:

```bash
grep -n \
    'WATCHER_VERSION' \
    /opt/lums-agent/watcher.py
```

Die aktuelle Watcher-Version ist:

```text
1.2.1
```

---

# 82. Den Watcher-Dienst prüfen

Inspizieren Sie die systemd-Unit:

```bash
systemctl cat \
    lums-agent-watcher.service
```

Der Dienst muss verweisen auf:

```text
/opt/lums-agent/watcher.py
```

Prüfen Sie, dass die Unit systemd bekannt ist:

```bash
systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Der Dienst kann inaktiv sein, wenn keine Ausführung ausgelöst wurde.

Dies ist für sich genommen kein Fehler.

---

# 83. Den Watcher-Timer prüfen

Bevor Sie den Watcher-Timer aktivieren, prüfen Sie, dass:

- `/etc/default/lums-agent` existiert und die korrekte Client-Konfiguration enthält.
- Der LUMS-Serverendpunkt und der Client-Token korrekt konfiguriert sind.
- Ein manueller Agent-Lauf erfolgreich war und der Server den Client-Bericht akzeptiert hat.
- Beide Watcher-Unit-Dateien aus dem Repository installiert wurden.

Aktivieren Sie den Timer nicht, während Authentifizierung oder Berichterstattung fehlschlagen.

Inspizieren Sie den Timer:

```bash
systemctl cat \
    lums-agent-watcher.timer
```

Aktivieren Sie den Timer erst, nachdem Sie alle oben genannten Voraussetzungen geprüft haben:

```bash
sudo systemctl enable --now \
    lums-agent-watcher.timer
```

Prüfen Sie:

```bash
systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

Inspizieren Sie die nächste geplante Ausführung:

```bash
systemctl list-timers \
    lums-agent-watcher.timer \
    --no-pager
```

---

# 84. Idle-bewusste Ausführung verstehen

Der Watcher kann Client-Idle-Informationen verwenden, bevor er Update-Jobs ausführt.

Der vorgesehene Ablauf ist:

```text
Pending job
    │
    ▼
Watcher
    │
    ▼
Idle detection
    │
    ├── idle state available
    │       │
    │       ▼
    │   idle threshold
    │       │
    │       ▼
    │   execute when allowed
    │
    └── idle state unavailable
            │
            ▼
        use configured
        fallback behavior
```

Idle-Erkennung darf niemals als Authentifizierung oder Autorisierung interpretiert werden.

Sie ist ausschließlich ein Ausführungsplanungsmechanismus.

---

# 85. Idle-Erkennung prüfen

Führen Sie den Idle-Erkennungspfad manuell über die installierte Agent/Watcher-Implementierung aus.

Inspizieren Sie das resultierende Dienstjournal:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 100 \
    --no-pager
```

Wenn die Plattform die erforderlichen Idle-Informationen nicht bereitstellt, kann der Client die Idle-Erkennung als nicht verfügbar melden.

Dies ist nicht automatisch ein Fehler.

Die wichtige Unterscheidung ist:

```text
idle_supported = available
```

versus:

```text
idle_supported = unavailable
```

Der Client darf nicht als idle angenommen werden, nur weil keine Idle-Informationen zurückgegeben wurden.

---

# 86. Einen kontrollierten Test-Update-Job erstellen

Beginnen Sie Installationstests nicht mit einem großen Systemupdate.

Verwenden Sie für den ersten Test ein kleines, bekanntes Paket.

Das Paket sollte:

```text
exist in the configured repository
be safe to install
be removable again
not be required by the operating system
```

Beispiel-Testpaket:

```text
sl
```

Bevor Sie den Job erstellen, prüfen Sie, ob es bereits installiert ist:

```bash
dpkg-query \
    -W \
    -f='${Status}\n' \
    sl \
    2>/dev/null || true
```

Verwenden Sie für Arch Linux ein Paket, das in den konfigurierten Repositories verfügbar und für einen umkehrbaren Test geeignet ist.

Verwenden Sie `sl` nicht blind auf jeder Distribution.

---

# 87. Paketsuche prüfen

Verwenden Sie die LUMS Package-Management-Oberfläche, um nach dem ausgewählten Paket zu suchen.

Der Suchablauf ist:

```text
Browser
   ↓
LUMS API
   ↓
Package Search Request
   ↓
Client
   ↓
APT / pacman
   ↓
Package Search Result
   ↓
LUMS API
   ↓
Browser
```

Prüfen Sie, dass das Ergebnis die erwarteten Informationen enthält:

```text
Package
Version
Description
Status
Action
```

Für Arch Linux können zusätzlich Repository-Informationen zurückgegeben werden.

---

# 88. Paketverwaltungsberechtigungen

Die Paketverwaltung ist durch RBAC eingeschränkt.

Administrator:

```text
Allowed
```

Operator:

```text
Allowed
```

Viewer:

```text
Not allowed
```

Ein Viewer darf keine Paketinstallation oder -entfernung durch direkten API-Aufruf ausführen.

Das Ausblenden der Funktion in der Browseroberfläche ist nur eine zusätzliche Benutzerfreundlichkeitseinschränkung.

Die serverseitige Autorisierung ist die tatsächliche Sicherheitsgrenze.

---

# 89. Paketinstallation testen

Erstellen Sie einen Installationsjob über die LUMS-Oberfläche.

Die logische Operation ist:

```text
INSTALL_PACKAGE
```

Der Job wird in der LUMS-Datenbank gespeichert, bevor der Agent ihn ausführt.

Der erwartete Ablauf ist:

```text
Create job
   ↓
PENDING
   ↓
Watcher detects job
   ↓
RUNNING
   ↓
Package manager
   ↓
SUCCESS
```

Überwachen Sie den Job in der LUMS-Oberfläche.

Ändern Sie die Datenbank nicht manuell, um einen Jobzustand zu erzwingen.

---

# 90. Das Installationsergebnis prüfen

Nachdem der Job Erfolg gemeldet hat, prüfen Sie das Paket lokal.

Unter Debian/Ubuntu:

```bash
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n' \
    sl
```

Prüfen Sie, dass der Paketmanager zustimmt:

```bash
apt-cache policy \
    sl
```

Das Paket muss tatsächlich installiert sein.

Ein LUMS-Status `SUCCESS` muss einer erfolgreichen clientseitigen Operation entsprechen.

---

# 91. Das Job-Ergebnis prüfen

Inspizieren Sie den LUMS-Job-Verlauf.

Prüfen Sie:

```text
Action
Package
Client
Start time
Completion time
Result
```

Das vom Client zurückgegebene Ergebnis muss vom Server validiert werden.

Ungültige oder unvollständige Ergebnisdaten dürfen nicht stillschweigend zu einem erfolgreichen Job werden.

Diese Validierung ist Teil des LUMS-Sicherheits- und Zuverlässigkeitsmodells.

---

# 92. Paketentfernung testen

Nach der Prüfung der Installation erstellen Sie einen Entfernungsjob:

```text
REMOVE_PACKAGE
```

Überwachen Sie:

```text
PENDING
   ↓
RUNNING
   ↓
SUCCESS
```

Nach Abschluss:

```bash
dpkg-query \
    -W \
    -f='${Status}\n' \
    sl \
    2>/dev/null || true
```

Das Paket sollte nicht mehr installiert sein.

Wenn das Paket vor dem Test nicht installiert war, behandeln Sie die Abwesenheit nicht als Beweis für eine erfolgreiche Entfernungsoperation.

---

# 93. Paketupdate testen

Paketupdates verwenden:

```text
UPDATE_PACKAGE
```

Der Server validiert, dass das angeforderte Paket ein verfügbares Update ist, bevor er den entsprechenden Job erstellt.

Der allgemeine Ablauf ist:

```text
Client reports available updates
       ↓
User selects package
       ↓
Server validates package
       ↓
Update job created
       ↓
Watcher executes
       ↓
Result reported
```

Konstruieren Sie keine Update-Anfragen manuell, die den normalen Validierungspfad umgehen.

---

# 94. Systemupdate testen

Ein vollständiges Systemupdate verwendet:

```text
UPDATE_SYSTEM
```

Diese Operation betrifft den Paketmanager-Zustand des Clients umfassender als eine Einzelpaketoperation.

Für den ersten Systemupdate-Test:

```text
Use a test client
Use a current backup
Monitor the console
Monitor the LUMS job
Do not interrupt the package manager
```

Verwenden Sie nicht den Produktionsserver selbst als erstes Systemupdate-Testziel.

---

# 95. Paketmanager-Sperren

APT und pacman können Paketmanager-Sperren verwenden.

Wenn eine Operation fehlschlägt, weil ein anderer Paketverwaltungsprozess aktiv ist, inspizieren Sie die laufenden Prozesse, bevor Sie Maßnahmen ergreifen.

Debian/Ubuntu:

```bash
ps aux | grep -E \
    '[a]pt|[d]pkg|[u]nattended'
```

Arch Linux:

```bash
ps aux | grep -E \
    '[p]acman|[p]ar'
```

Löschen Sie keine Paketmanager-Lockdateien, während der Paketmanager tatsächlich läuft.

Eine Sperre schützt normalerweise vor gleichzeitigen Paketoperationen.

---

# 96. LUMS-Fehler von Paketmanager-Fehlern unterscheiden

Wenn ein Job fehlschlägt, bestimmen Sie, welche Schicht fehlgeschlagen ist.

```text
LUMS API
   │
   ├── Job creation failure
   │
   ▼
LUMS database
   │
   ├── State / persistence problem
   │
   ▼
Watcher
   │
   ├── Execution problem
   │
   ▼
Package manager
   │
   ├── APT / pacman failure
   │
   ▼
Operating system
```

Inspizieren Sie das Client-Journal:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Inspizieren Sie den LUMS-Container:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Wiederholen Sie einen fehlgeschlagenen Job nicht sofort, ohne zu bestimmen, warum er fehlgeschlagen ist.

---

# 97. Job-Checkpointing prüfen

LUMS verfolgt Job- und Paket-Element-Zustände.

Für paketbasierte Jobs können einzelne Paket-Elemente gecheckpointet werden.

Das vorgesehene Verhalten ist:

```text
Package A → SUCCESS
Package B → SUCCESS
Package C → RUNNING
             │
             ▼
          interruption
             │
             ▼
          recovery
             │
             ▼
Package A → not repeated
Package B → not repeated
Package C → resumed / handled
```

Dies verhindert, dass abgeschlossene Paketoperationen nach einer Unterbrechung unnötig wiederholt werden.

---

# 98. Kontrollierte Job-Wiederherstellung testen

Verwenden Sie einen nicht kritischen Testjob.

Starten Sie den Job und beobachten Sie seinen Zustand:

```text
PENDING
```

dann:

```text
RUNNING
```

Unterbrechen Sie absichtlich kein Produktionsupdate.

Verwenden Sie für Wiederherstellungstests einen dedizierten Testclient und eine kontrollierte Paketoperation.

Starten Sie nach einer Unterbrechung oder einem simulierten Fehler den Watcher neu:

```bash
sudo systemctl restart \
    lums-agent-watcher.timer
```

Inspizieren Sie dann:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Prüfen Sie, dass bereits erfolgreiche Paket-Elemente nicht unnötig erneut ausgeführt werden.

---

# 99. Reboot-Erkennung prüfen

Einige Paketoperationen können einen Reboot erfordern.

Der Agent/Watcher meldet Reboot-Anforderungen an LUMS.

Der allgemeine Ablauf ist:

```text
Package operation
      ↓
Reboot requirement detected
      ↓
Result reported
      ↓
LUMS records reboot state
```

Prüfen Sie nach einer Testoperation, die legitimerweise einen Reboot erfordert, das entsprechende Job-Ergebnis in der LUMS-Oberfläche.

Booten Sie einen Produktionsclient nicht nur zum Testen des Mechanismus neu, es sei denn, das System ist für diesen Test vorgesehen.

---

# 100. Berichterstattung nach Reboot prüfen

Wenn ein Testclient neu gebootet wird, prüfen Sie, dass:

```text
systemd
   ↓
LUMS Agent timer
   ↓
Agent report
   ↓
LUMS server
```

weiterhin funktioniert.

Prüfen Sie:

```bash
systemctl status \
    lums-agent.timer \
    --no-pager
```

und:

```bash
systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

Inspizieren Sie dann den neuesten Bericht in der LUMS-Oberfläche.

---

# 101. Update-Erkennung prüfen

Führen Sie den Agent manuell aus:

```bash
sudo systemctl start \
    lums-agent.service
```

Inspizieren Sie:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Der Client sollte melden:

```text
Installed packages
Available updates
Agent status
```

Der Server sollte den aktuellen Zustand des Clients aktualisieren.

Verwechseln Sie nicht:

```text
available updates
```

mit:

```text
installed packages
```

Sie repräsentieren unterschiedliche Datensätze.

---

# 102. Installierte Software prüfen

Öffnen Sie den Bereich „Installierte Software“ des Clients in LUMS.

Die Paketliste sollte dem clientseitigen Paketmanager entsprechen.

Für Debian/Ubuntu:

```bash
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n'
```

Für Arch:

```bash
pacman -Q
```

Das LUMS-Inventar ist informativ, bis ausdrücklich ein Job erstellt wird.

Der Filter für installierte Pakete verändert nicht selbst den Client.

---

# 103. Paketsuche separat prüfen

Die Paketsuche im Package Management ist vom Filter für installierte Pakete getrennt.

Die Unterscheidung ist:

```text
Installed Package Filter
    ↓
Searches the package inventory already reported by the client

Package Management Search
    ↓
Requests package information from the client's package manager
```

Behandeln Sie die beiden Suchfunktionen nicht als austauschbar.

Ein Paket kann über APT oder pacman verfügbar sein, ohne installiert zu sein.

---

# 104. Viewer-Paketisolation prüfen

Melden Sie sich als Viewer an.

Prüfen Sie, dass die Package-Management-Oberfläche nicht verfügbar ist.

Prüfen Sie dann die serverseitige Einschränkung, indem Sie eine nicht autorisierte Paketverwaltungsanfrage über eine genehmigte Testmethode versuchen.

Die Anfrage muss abgelehnt werden.

Viewer-Zugriff muss schreibgeschützt bleiben.

---

# 105. Operator-Paketverwaltung prüfen

Melden Sie sich als Operator an.

Prüfen Sie den Zugriff auf:

```text
Package Search
Package Installation
Package Removal
Package Updates
Update Jobs
Update History
```

Der Operator darf keinen Zugriff auf ausschließlich für Administratoren vorgesehene Benutzerverwaltungsfunktionen erhalten.

---

# 106. Administrator-Paketverwaltung prüfen

Melden Sie sich als Administrator an.

Prüfen Sie dieselben Paketverwaltungsfähigkeiten wie beim Operator.

Prüfen Sie zusätzlich den Zugriff auf:

```text
User Management
Client Management
Client Token Rotation
```

Administratorberechtigungen müssen serverseitig durchgesetzt bleiben.

---

# 107. Erster End-to-End-Pakettest

Der erste vollständige Paketverwaltungstest sollte dieser Reihenfolge folgen:

```text
1. Client reports successfully
2. Package search succeeds
3. Package result is displayed
4. Administrator/Operator creates INSTALL_PACKAGE job
5. Job becomes PENDING
6. Watcher detects the job
7. Job becomes RUNNING
8. Package manager executes
9. Client reports result
10. Server validates result
11. Job becomes SUCCESS
12. Installed package is verified locally
13. Package is visible in LUMS inventory
```

Erst nachdem diese Sequenz erfolgreich war, sollte mit breiteren Update-Tests begonnen werden.

---

# 108. Client-Ausführungs-Checkpoint

Prüfen Sie:

```text
[ ] Watcher installed
[ ] Watcher version verified
[ ] Watcher timer enabled
[ ] Idle detection works or reports unavailable correctly
[ ] Package search works
[ ] Package installation works
[ ] Package removal works
[ ] Package update works
[ ] System update path is available
[ ] Job states transition correctly
[ ] Job results are validated
[ ] Package checkpointing works
[ ] Reboot detection works
[ ] Reporting continues after reboot
[ ] Viewer cannot mutate package state
[ ] Operator can manage packages
[ ] Administrator can manage packages
```

An diesem Punkt ist der Kern-Ausführungspfad des LUMS-Clients installiert und validiert.

Der nächste Abschnitt behandelt vollständige End-to-End-Validierung, RBAC-Verifikation, Backup/Wiederherstellung, Wartung, Upgrades und abschließende Installationsprüfungen.

# 109. Vollständige End-to-End-Validierung

Nachdem der Server und mindestens ein Linux-Client konfiguriert wurden, führen Sie eine vollständige End-to-End-Validierung durch.

Der vollständige LUMS-Pfad ist:

```text
Browser
   │
   ▼
Nginx / HTTPS
   │
   ▼
LUMS API
   │
   ▼
SQLite
   │
   ▼
Client Agent
   │
   ▼
Package Manager
   │
   ▼
Update Result
   │
   ▼
SQLite
   │
   ▼
Web Interface
```

Betrachten Sie die Installation nicht als abgeschlossen, nur weil sich die Weboberfläche öffnet.

Alle wichtigen Schichten müssen verifiziert werden.

---

# 110. Server-Gesundheitsprüfung

Prüfen Sie den LUMS-Container:

```bash
sudo docker ps \
    --filter name=lums
```

Prüfen Sie den Containerzustand:

```bash
sudo docker inspect \
    lums \
    --format '{{.State.Status}}'
```

Erwartet:

```text
running
```

Inspizieren Sie die letzten Logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Die Logs sollten keinen aktiven Start- oder Migrationsfehler enthalten.

---

# 111. Container-Sicherheitsprüfung

Prüfen Sie die Laufzeit-Sicherheitskonfiguration:

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'
```

Erwartete Basis:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

Prüfen Sie die Netzwerkbindung:

```bash
sudo docker port \
    lums
```

Erwartet:

```text
5000/tcp -> 127.0.0.1:5050
```

---

# 112. Persistenten Speicher prüfen

Prüfen Sie das LUMS-Volume:

```bash
sudo docker volume inspect \
    lums-data
```

Prüfen Sie, dass die Anwendungsdatenbank existiert:

```bash
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db
```

Die Datenbank muss im persistenten Speicher liegen.

Speichern Sie die Produktionsdatenbank nicht nur im Container-Dateisystem.

---

# 113. SQLite-Gesundheitsprüfung

Inspizieren Sie die aktuelle SQLite-Laufzeitkonfiguration:

```bash
sudo docker exec -i lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

for name in (
    "journal_mode",
    "busy_timeout",
    "synchronous",
    "foreign_keys",
):
    value = db.execute(
        f"PRAGMA {name}"
    ).fetchone()[0]
    print(f"{name}={value}")

db.close()
PY
```

Die aktuelle Basis ist:

```text
journal_mode=wal
busy_timeout=5000
synchronous=2
foreign_keys=0
```

Die Anwendung aktiviert ausdrücklich die Fremdschlüssel-Durchsetzung.

---

# 114. SQLite-Integritätsprüfung

Führen Sie aus:

```bash
sudo docker exec -i lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

result = db.execute(
    "PRAGMA integrity_check"
).fetchone()[0]

print(result)

db.close()
PY
```

Erwartet:

```text
ok
```

Fahren Sie bei einer neuen Produktionsrollout nicht fort, wenn die Integritätsprüfung Beschädigung meldet.

---

# 115. Datenbankmigrationen prüfen

Inspizieren Sie den Migrationszustand:

```bash
sudo docker logs \
    --tail 200 \
    lums | grep -i migration
```

Die Anwendung muss ihre konfigurierten Migrationen vor dem normalen Betrieb abschließen.

Ändern Sie die Migration-State-Tabelle nicht manuell, es sei denn, das aktuelle LUMS-Migrationsverfahren verlangt dies ausdrücklich.

---

# 116. Die automatisierte Testsuite ausführen

Auf der LUMS-Entwicklungs-/Testumgebung:

```bash
cd /opt/lums-public
```

Führen Sie aus:

```bash
./.venv-test/bin/pytest -q
```

Die Anzahl der Tests ändert sich, während sich das Projekt weiterentwickelt; verlassen Sie sich auf das Ergebnis des Befehls, nicht auf eine feste Anzahl in diesem Dokument.

Die wichtige Anforderung ist:

```text
all tests pass
```

Ignorieren Sie fehlschlagende Tests nicht, weil die Produktionsweboberfläche funktional erscheint.

---

# 117. RBAC prüfen

Das aktuelle Rollenmodell ist:

| Funktion               | Administrator | Operator | Viewer |
| ---------------------- | ------------: | -------: | -----: |
| Clients anzeigen       |           Ja |      Ja |    Ja |
| Installierte Software  |           Ja |      Ja |    Ja |
| Verfügbare Updates     |           Ja |      Ja |    Nein |
| Jobs erstellen/ausführen |         Ja |      Ja |    Nein |
| Update-Verlauf         |           Ja |      Ja |    Nein |
| Paketverwaltung        |           Ja |      Ja |    Nein |
| Systemwartung          |           Ja |      Ja |    Nein |
| Clients erstellen/deaktivieren |  Ja |      Nein |    Nein |
| Client-Tokens rotieren |           Ja |      Nein |    Nein |
| Benutzerverwaltung     |           Ja |      Nein |    Nein |
| Rollenverwaltung       |           Ja |      Nein |    Nein |

Die Oberfläche sollte diese Berechtigungen widerspiegeln.

Wichtiger ist, dass die API sie unabhängig durchsetzt.

---

# 118. Administratorzugriff prüfen

Melden Sie sich als Administrator an.

Prüfen Sie den Zugriff auf:

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
User management
```

Prüfen Sie Client-Management-Funktionen:

```text
Create client
Disable client
Rotate client token
```

Der Administrator sollte diese Operationen durchführen können.

---

# 119. Operatorzugriff prüfen

Melden Sie sich als Operator an.

Prüfen Sie den Zugriff auf:

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
```

Prüfen Sie, dass ausschließlich für Administratoren vorgesehene Funktionalität nicht verfügbar ist:

```text
User management
Role management
Client creation/disabling
Client-token rotation
```

Verlassen Sie sich nicht nur auf ausgeblendete UI-Elemente.

Geschützte API-Operationen müssen nicht autorisierte Anfragen ablehnen.

---

# 120. Viewerzugriff prüfen

Melden Sie sich als Viewer an.

Der Viewer sollte zugreifen können auf:

```text
Clients
Installed software
```

Das Folgende darf nicht verfügbar sein:

```text
Available updates
Update jobs
Update history
Package management
System maintenance
```

Der Viewer darf den Clientzustand nicht verändern können.

---

# 121. Client-Authentifizierung prüfen

Bestätigen Sie, dass jeder Client seinen eigenen Bearer-Token verwendet.

Das erwartete Modell ist:

```text
Client A → Token A
Client B → Token B
Client C → Token C
```

Teilen Sie Tokens nicht zwischen Clients.

Prüfen Sie, dass ein rotierter oder widerrufener Token nicht mehr akzeptiert wird.

Legen Sie niemals echte Tokens in Testausgaben oder Dokumentation ab.

---

# 122. Update-Erkennung prüfen

Auf einem Testclient:

```bash
sudo systemctl start \
    lums-agent.service
```

Inspizieren Sie:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Prüfen Sie dann den Client in der LUMS-Oberfläche.

Die gemeldeten Informationen sollten das aktuelle Paketinventar und Update-Informationen enthalten, wo unterstützt.

---

# 123. Erstellung von Update-Jobs prüfen

Erstellen Sie einen kontrollierten Update-Job über die LUMS-Oberfläche.

Der Job sollte anfangs erscheinen als:

```text
PENDING
```

Der Watcher verarbeitet dann den Job:

```text
PENDING
   ↓
RUNNING
   ↓
SUCCESS
```

oder:

```text
PENDING
   ↓
RUNNING
   ↓
FAILED
```

abhängig vom tatsächlichen Operationsergebnis.

Ändern Sie den Datenbankzustand nicht manuell.

---

# 124. Job-Ausführung prüfen

Inspizieren Sie den Client-Watcher:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Inspizieren Sie den LUMS-Server:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Vergleichen Sie den serverseitigen Jobzustand mit dem clientseitigen Ausführungsergebnis.

Beide müssen übereinstimmen.

---

# 125. Validierung von Paketergebnissen prüfen

Ein Job darf nicht allein deshalb erfolgreich werden, weil der Client eine syntaktisch gültige Antwort gesendet hat.

Der Server validiert das zurückgegebene Ergebnis.

Prüfen Sie dies über die automatisierten Ergebnisvalidierungstests:

```bash
./.venv-test/bin/pytest -q \
    tests/test_job_result.py
```

Ein erfolgreiches Ergebnis muss die erwartete Struktur und einen gültigen Jobkontext enthalten.

Fehlerhafte oder inkonsistente Ergebnisse müssen abgelehnt werden.

---

# 126. Job-Wiederherstellung prüfen

Verwenden Sie einen dedizierten Testclient für Wiederherstellungstests.

Das Wiederherstellungsmodell ist:

```text
Job
 │
 ├── package item A → SUCCESS
 ├── package item B → SUCCESS
 └── package item C → interrupted
                       │
                       ▼
                    recovery
                       │
                       ▼
                  resume safely
```

Nach der Wiederherstellung dürfen zuvor erfolgreiche Paket-Elemente nicht unnötig wiederholt werden.

Inspizieren Sie:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Prüfen Sie dann den endgültigen Jobzustand in LUMS.

---

# 127. Reboot-Erkennung prüfen

Für ein kontrolliertes Testupdate, das einen Reboot erfordert, prüfen Sie, dass der Client die Reboot-Anforderung meldet.

Nach dem Reboot:

```bash
systemctl status \
    lums-agent.timer \
    --no-pager
```

und:

```bash
systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

Der Client muss nach dem Booten die normale Berichterstattung wieder aufnehmen.

---

# 128. Audit-Logging prüfen

Führen Sie eine kontrollierte administrative Aktion durch und inspizieren Sie dann das LUMS-Audit-Log.

Relevante Operationen umfassen:

```text
Login
User creation
Client creation
Client-token rotation
Job creation
Package management
```

Audit-Einträge sollten genügend Informationen bieten, um die administrative Aktion zu rekonstruieren, ohne Secrets offenzulegen.

Loggen Sie nicht:

```text
Passwords
Client tokens
Application secrets
Private keys
Session secrets
```

---

# 129. Log-Redaktion prüfen

Inspizieren Sie die letzten Logs:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Inspizieren Sie Client-Logs:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

und:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Authentifizierungsdaten und Secrets dürfen nicht in normaler Diagnoseausgabe erscheinen.

Wenn ein Diagnosebefehl ein Secret offenlegen würde, fügen Sie seine Ausgabe nicht in ein Issue, einen Commit oder eine Dokumentation ein.

---

# 130. Netzwerkexposition prüfen

Inspizieren Sie lauschende Ports:

```bash
sudo ss -lntp
```

Der LUMS-Anwendungsport sollte bleiben:

```text
127.0.0.1:5050
```

Nginx stellt den externen Dienst bereit:

```text
:80
:443
```

Die Anwendung darf nicht direkt exponiert werden über:

```text
0.0.0.0:5050
```

oder:

```text
0.0.0.0:5000
```

---

# 131. Firewall-Konfiguration prüfen

Wenn eine Host-Firewall aktiviert ist, inspizieren Sie sie:

```bash
sudo ufw status verbose
```

Die Bereitstellung sollte nur die vom Host benötigten Dienste exponieren.

Erstellen Sie keine Firewall-Regel für Port `5050`, nur weil Docker diesen Port intern verwendet.

Die vorgesehene Architektur ist:

```text
LAN
 │
 ▼
443
 │
 ▼
Nginx
 │
 ▼
127.0.0.1:5050
 │
 ▼
LUMS
```

---

# 132. Backup-Strategie

Die LUMS-SQLite-Datenbank ist persistenter Anwendungszustand.

Backups sollten mindestens schützen:

```text
LUMS database
TLS material
LUMS application secret
Deployment configuration
```

Backups müssen außerhalb des aktiven LUMS-Containers gespeichert werden.

Speichern Sie Backups nicht in:

```text
/app
```

und verlassen Sie sich nicht auf das Container-Dateisystem.

Das Docker-Volume:

```text
lums-data
```

enthält persistente Anwendungsdaten, aber ein Docker-Volume ist selbst kein Backup.

---

# 133. Datenbank-Backup

Bevor Sie die Datenbank sichern, identifizieren Sie die Datenbankdatei:

```bash
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db
```

Ein Datenbank-Backup sollte mit einem konsistenten SQLite-Backup-Mechanismus durchgeführt werden.

Kopieren Sie eine laufende SQLite-Datenbank nicht blind, während sie verändert wird, wenn das Backup-Verfahren keine Konsistenz garantieren kann.

Nach dem Erstellen eines Backups prüfen Sie, dass die Backup-Datei existiert und geschützt ist.

---

# 134. Konfigurations-Backup

Schützen Sie folgendes Bereitstellungsmaterial:

```text
/etc/lums/secrets/
/etc/lums/tls/
/etc/nginx/sites-available/lums
/etc/nginx/sites-enabled/lums
```

Veröffentlichen Sie diese Dateien nicht.

Die folgenden Dateien sind besonders sensibel:

```text
/etc/lums/secrets/lums_secret
/etc/lums/tls/lums.key
```

Schützen Sie Backup-Berechtigungen entsprechend.

---

# 135. Wiederherstellungsplanung

Eine Wiederherstellung sollte auf einem Nicht-Produktionssystem getestet werden, bevor sie für Disaster Recovery benötigt wird.

Die Wiederherstellungssequenz ist konzeptionell:

```text
Backup
  ↓
Verify backup integrity
  ↓
Prepare clean LUMS host
  ↓
Restore secret/configuration
  ↓
Restore database
  ↓
Restore TLS material
  ↓
Start LUMS
  ↓
Run integrity checks
  ↓
Validate users/clients/jobs
```

Überschreiben Sie keine Produktionsdatenbank, ohne zuvor den bestehenden Zustand zu sichern.

---

# 136. Datenbank-Wiederherstellung prüfen

Nach dem Wiederherstellen einer Datenbank führen Sie aus:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

print(
    db.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]
)

db.close()
PY
```

Erwartet:

```text
ok
```

Prüfen Sie dann:

```text
users
clients
update jobs
package data
audit data
```

Gehen Sie nicht davon aus, dass eine erfolgreiche SQLite-Integritätsprüfung beweist, dass der vollständige Anwendungszustand korrekt ist.

---

# 137. Wartungsprinzipien

Routinemäßige Wartung sollte folgen:

```text
Observe
   ↓
Back up
   ↓
Change
   ↓
Verify
```

Führen Sie keine unzusammenhängende Wartung während eines aktiven Update-Jobs durch.

Vor der Wartung:

```bash
sudo docker ps \
    --filter name=lums
```

Prüfen Sie aktive Jobs in der LUMS-Oberfläche.

Wenn ein Update läuft, lassen Sie es abschließen, es sei denn, die Wartungsoperation erfordert ausdrücklich eine Unterbrechung.

---

# 138. Container-Wartung

Inspizieren Sie das laufende Image:

```bash
sudo docker inspect \
    lums \
    --format '{{.Config.Image}}'
```

Inspizieren Sie den Container:

```bash
sudo docker ps \
    --filter name=lums
```

Inspizieren Sie die letzten Logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Entfernen Sie das persistente Volume nicht während gewöhnlicher Container-Wartung.

Das Volume enthält Anwendungszustand.

---

# 139. Image-Wartung

Bevor Sie das Produktionsimage ersetzen:

```bash
cd /opt/lums-public
```

Führen Sie die automatisierten Tests aus:

```bash
./.venv-test/bin/pytest -q
```

Bauen Sie das neue Image:

```bash
sudo docker build \
    -t lums:new \
    .
```

Ersetzen Sie den laufenden Container nicht, bis das Image die erforderliche Validierung bestanden hat.

Halten Sie den aktuell funktionierenden Container verfügbar, bis der Ersatz verifiziert wurde.

---

# 140. Kontrollierter Container-Austausch

Beim Ersetzen des Produktionscontainers:

```text
Current container
       │
       ▼
Backup / checkpoint
       │
       ▼
Build new image
       │
       ▼
Validate image
       │
       ▼
Stop old container
       │
       ▼
Start new container
       │
       ▼
Validate runtime
       │
       ▼
Validate HTTPS
       │
       ▼
Validate application
```

Das persistente Volume muss bleiben:

```text
lums-data
```

Der Secret-Mount muss schreibgeschützt bleiben.

Der Anwendungsport muss auf localhost beschränkt bleiben.

---

# 141. Laufzeit-Sicherheit nach Ersatz prüfen

Nach jedem Container-Austausch wiederholen Sie:

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'
```

Prüfen Sie:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

Prüfen Sie außerdem:

```bash
sudo docker port \
    lums
```

Erwartet:

```text
5000/tcp -> 127.0.0.1:5050
```

---

# 142. Persistente Daten nach Ersatz prüfen

Nach dem Starten des Ersatzcontainers:

```bash
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db
```

Dann:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
db.close()
PY
```

Erwartet:

```text
ok
```

Prüfen Sie schließlich über die LUMS-Oberfläche, dass bestehende Benutzer und Clients weiterhin vorhanden sind.

---

# 143. Wartungsabschluss-Checkpoint

Prüfen Sie nach der Wartung:

```text
[ ] Container running
[ ] Runtime hardening intact
[ ] Persistent volume mounted
[ ] Database accessible
[ ] SQLite integrity check passes
[ ] Nginx running
[ ] HTTPS working
[ ] Login working
[ ] Existing users present
[ ] Existing clients present
[ ] Agent reporting working
[ ] Watcher working
[ ] Update jobs working
[ ] Audit logging working
```

Erst nach diesen Prüfungen ist die Wartungsoperation abgeschlossen.

---

# 144. Installationszustand zu diesem Zeitpunkt

Eine korrekt installierte LUMS-Umgebung besteht nun aus:

```text
                    ┌──────────────────────┐
                    │       Browser        │
                    └──────────┬───────────┘
                               │ HTTPS
                               ▼
                    ┌──────────────────────┐
                    │        Nginx         │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    LUMS Container    │
                    │                      │
                    │ Flask / Gunicorn     │
                    │ RBAC                 │
                    │ CSRF                 │
                    │ Audit Logging        │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │       SQLite         │
                    │     lums-data        │
                    └──────────┬───────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
                ▼                             ▼
        ┌──────────────┐              ┌──────────────┐
        │ LUMS Agent   │              │ LUMS Watcher │
        │ 1.7.0        │              │ 1.2.1        │
        └──────┬───────┘              └──────┬───────┘
               │                             │
               ▼                             ▼
        Inventory / Report             Update Jobs
               │                             │
               └──────────────┬──────────────┘
                              ▼
                       APT / pacman
```

Dies ist die vorgesehene Betriebsarchitektur.

Der nächste Abschnitt behandelt Upgrades, Deinstallation und die abschließende Installationscheckliste.

# 145. Upgrade-Verfahren

LUMS-Upgrades sollten in kontrollierten Schritten durchgeführt werden.

Die empfohlene Sequenz ist:

```text
Review
   ↓
Backup
   ↓
Test
   ↓
Build
   ↓
Deploy
   ↓
Validate
```

Aktualisieren Sie die Produktionsinstallation nicht allein deshalb, weil eine neue Git-Revision existiert.

Überprüfen Sie zuerst die Änderungen:

```bash
cd /opt/lums-public

git status
git log --oneline -10
```

Überprüfen Sie die relevanten Anwendungs-, Agent- und Migrationsänderungen vor der Bereitstellung.

---

# 146. Pre-Upgrade-Backup erstellen

Bevor Sie den Produktionscontainer ersetzen, erstellen Sie ein aktuelles Backup des persistenten LUMS-Zustands.

Prüfen Sie das aktive Volume:

```bash
sudo docker inspect \
    lums \
    --format '{{json .Mounts}}'
```

Bestätigen Sie, dass:

```text
lums-data
```

weiterhin gemountet ist unter:

```text
/var/lib/lums
```

Schützen Sie außerdem die externe Konfiguration:

```text
/etc/lums/secrets/
/etc/lums/tls/
/etc/nginx/
```

Fahren Sie nicht mit einem Upgrade fort, wenn das erforderliche Backup nicht verifiziert werden kann.

---

# 147. Unnötige Änderungen während eines Upgrades stoppen

Prüfen Sie vor dem Upgrade aktive Jobs in der LUMS-Oberfläche.

Vermeiden Sie es, die Anwendung zu ersetzen, während ein kritischer Update-Job aktiv ausgeführt wird.

Warten Sie bei Bedarf, bis der Job einen Endzustand erreicht:

```text
SUCCESS
```

oder:

```text
FAILED
```

Ändern Sie einen Job nicht manuell von `RUNNING` zu `SUCCESS` oder `FAILED`, nur um ein Upgrade zu ermöglichen.

---

# 148. Das Repository aktualisieren

Wechseln Sie in das Repository:

```bash
cd /opt/lums-public
```

Inspizieren Sie den aktuellen Zustand:

```bash
git status
```

Aktualisieren Sie das Repository mit dem normalen Projektworkflow.

Nach der Aktualisierung:

```bash
git log --oneline -5
```

Prüfen Sie, dass die vorgesehene Revision ausgecheckt ist.

Stellen Sie kein Repository bereit, das unbeabsichtigte lokale Änderungen enthält.

Wenn lokale Änderungen vorhanden sind:

```bash
git status
```

Überprüfen Sie sie, bevor Sie fortfahren.

---

# 149. Die Testsuite vor dem Bauen ausführen

Führen Sie aus:

```bash
./.venv-test/bin/pytest -q
```

Alle Tests müssen bestehen.

Eine geänderte Testanzahl ist nicht automatisch ein Problem. Die Anforderung ist, dass die vollständige Suite erfolgreich abgeschlossen wird.

---

# 150. Das aktualisierte Image bauen

Bauen Sie ein neues Image, ohne sofort den laufenden Container zu ersetzen:

```bash
sudo docker build \
    -t lums:new \
    .
```

Prüfen Sie das Image:

```bash
sudo docker image inspect \
    lums:new
```

Der Build muss erfolgreich abgeschlossen werden.

Verwenden Sie kein fehlgeschlagenes oder teilweise gebautes Image für die Produktionsbereitstellung.

---

# 151. Das aktualisierte Image prüfen

Überprüfen Sie die Image-Metadaten:

```bash
sudo docker image inspect \
    lums:new \
    --format '
User={{.Config.User}}
Entrypoint={{json .Config.Entrypoint}}
Cmd={{json .Config.Cmd}}
'
```

Das Image muss das erwartete Non-Root-Anwendungsmodell erhalten.

Die Produktionslaufzeit muss weiterhin bieten:

```text
read-only root filesystem
dropped Linux capabilities
no-new-privileges
read-only secret mount
persistent application volume
localhost-only application port
```

---

# 152. Den Produktionscontainer ersetzen

Wenn das neue Image die Validierung bestanden hat, ersetzen Sie den laufenden Container mit der etablierten gehärteten Konfiguration.

Stoppen Sie den bestehenden Container:

```bash
sudo docker stop \
    lums
```

Entfernen Sie nur den Container:

```bash
sudo docker rm \
    lums
```

Entfernen Sie **nicht**:

```text
lums-data
```

Starten Sie den Ersatz mit der gehärteten Laufzeit:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --security-opt=no-new-privileges:true \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --tmpfs /run:rw,noexec,nosuid,size=16m \
    -p 127.0.0.1:5050:5000 \
    -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
    -v lums-data:/var/lib/lums \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    lums:new
```

---

# 153. Den Ersatzcontainer prüfen

Prüfen Sie:

```bash
sudo docker ps \
    --filter name=lums
```

Dann:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Prüfen Sie die Laufzeit:

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'
```

Erwartet:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

---

# 154. Anwendungsverfügbarkeit prüfen

Prüfen Sie den lokalen Anwendungsendpunkt:

```bash
curl -I \
    http://127.0.0.1:5050/
```

Testen Sie dann den öffentlichen HTTPS-Pfad:

```bash
curl -I \
    https://LUMS-SERVER/
```

Prüfen Sie den Login über den Browser.

Betrachten Sie das Upgrade nicht als abgeschlossen, bis auch der externe HTTPS-Pfad getestet wurde.

---

# 155. Persistenten Zustand nach Upgrade prüfen

Prüfen Sie die Datenbank:

```bash
sudo docker exec lums \
    ls -lh /var/lib/lums/lums.db
```

Führen Sie aus:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
db.close()
PY
```

Erwartet:

```text
ok
```

Prüfen Sie über die Weboberfläche, dass:

```text
users
clients
jobs
audit history
package information
```

weiterhin verfügbar sind.

---

# 156. Client-Kommunikation nach Upgrade prüfen

Führen Sie den Agent auf einem Testclient aus:

```bash
sudo systemctl start \
    lums-agent.service
```

Inspizieren Sie:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Prüfen Sie, dass der Server den Bericht akzeptiert.

Prüfen Sie dann den Client in der LUMS-Oberfläche.

---

# 157. Update-Ausführung nach Upgrade prüfen

Erstellen Sie einen kontrollierten Testjob.

Prüfen Sie:

```text
PENDING
   ↓
RUNNING
   ↓
SUCCESS
```

oder einen erwarteten:

```text
FAILED
```

Zustand, wenn die Operation tatsächlich fehlschlägt.

Inspizieren Sie den Watcher:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Dies bestätigt, dass das Upgrade den Ausführungspfad nicht beschädigt hat.

---

# 158. Sicherheitsbasis nach Upgrade prüfen

Jedes Produktionsupgrade muss die Sicherheitsbasis erhalten.

Prüfen Sie:

```text
[ ] HTTPS
[ ] Bearer client authentication
[ ] RBAC
[ ] CSRF protection
[ ] Audit logging
[ ] Non-root container
[ ] Read-only root filesystem
[ ] Capabilities dropped
[ ] no-new-privileges
[ ] Protected secret mount
[ ] Persistent data volume
[ ] Localhost-only Docker port
[ ] Firewall policy
```

Ein funktionales Upgrade, das diese Eigenschaften schwächt, gilt nicht als abgeschlossen.

---

# 159. Rollback-Verfahren

Wenn der neue Container die Validierung nicht besteht, zerstören Sie nicht sofort die vorherigen Bereitstellungsinformationen.

Inspizieren Sie zuerst:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Wenn das vorherige Image noch verfügbar ist:

```bash
sudo docker images
```

Stellen Sie das zuvor validierte Image mit derselben gehärteten Container-Konfiguration wieder her.

Das persistente Volume bleibt:

```text
lums-data
```

Stellen Sie kein Datenbank-Backup wieder her, nur weil der Anwendungscontainer ersetzt wurde.

Stellen Sie die Datenbank nur wieder her, wenn die Datenbank selbst wiederhergestellt werden muss.

---

# 160. Vorbereitung der Deinstallation

Bevor Sie LUMS deinstallieren, entscheiden Sie, ob die persistenten Anwendungsdaten erhalten bleiben müssen.

Das Folgende sind separate Ressourcen:

```text
Container
Image
Persistent volume
Configuration
TLS material
Nginx configuration
Client installations
```

Das Entfernen des Containers entfernt nicht das Docker-Volume.

Diese Unterscheidung ist beabsichtigt.

---

# 161. Den LUMS-Container entfernen

Stoppen Sie den Container:

```bash
sudo docker stop \
    lums
```

Entfernen Sie ihn:

```bash
sudo docker rm \
    lums
```

Prüfen Sie:

```bash
sudo docker ps -a \
    --filter name=lums
```

Das persistente Volume ist weiterhin vorhanden, es sei denn, es wird ausdrücklich entfernt.

---

# 162. Das LUMS-Docker-Image entfernen

Listen Sie Images auf:

```bash
sudo docker images \
    'lums*'
```

Entfernen Sie nur Images, die nicht mehr benötigt werden:

```bash
sudo docker rmi \
    lums:new
```

Wiederholen Sie dies für andere veraltete lokale LUMS-Images nach Bedarf.

Entfernen Sie nicht das Image, das derzeit für einen Rollback benötigt wird, bevor die Installation vollständig außer Betrieb genommen wurde.

---

# 163. Das persistente Volume entfernen

Führen Sie diesen Schritt nur durch, wenn die LUMS-Datenbank nicht mehr benötigt wird.

Prüfen Sie:

```bash
sudo docker volume inspect \
    lums-data
```

Erstellen Sie bei Bedarf ein abschließendes Backup.

Entfernen Sie dann:

```bash
sudo docker volume rm \
    lums-data
```

Dies entfernt dauerhaft die persistenten Anwendungsdaten, die in diesem Volume gespeichert sind.

Führen Sie diesen Befehl nicht während normaler Upgrades aus.

---

# 164. LUMS-Serverkonfiguration entfernen

Wenn der Server dauerhaft außer Betrieb genommen wird, entfernen Sie die LUMS-spezifische Konfiguration:

```text
/etc/lums/
/etc/nginx/sites-available/lums
/etc/nginx/sites-enabled/lums
```

Entfernen Sie die Nginx-Site:

```bash
sudo rm -f \
    /etc/nginx/sites-enabled/lums
```

Entfernen Sie die Konfiguration:

```bash
sudo rm -f \
    /etc/nginx/sites-available/lums
```

Validieren Sie dann Nginx:

```bash
sudo nginx -t
```

Laden Sie neu:

```bash
sudo systemctl reload nginx
```

Entfernen Sie `/etc/lums/` erst, nachdem Sie geprüft haben, dass keine andere Anwendung davon abhängt.

---

# 165. Client-Installationen entfernen

LUMS-Clients müssen separat außer Betrieb genommen werden.

Deaktivieren Sie den Agent-Timer:

```bash
sudo systemctl disable --now \
    lums-agent.timer
```

Deaktivieren Sie den Watcher-Timer:

```bash
sudo systemctl disable --now \
    lums-agent-watcher.timer
```

Stoppen Sie alle verbleibenden Dienste:

```bash
sudo systemctl stop \
    lums-agent.service \
    lums-agent-watcher.service
```

Entfernen Sie die installierten systemd-Units:

```bash
sudo rm -f \
    /etc/systemd/system/lums-agent.service \
    /etc/systemd/system/lums-agent-watcher.service \
    /etc/systemd/system/lums-agent.timer \
    /etc/systemd/system/lums-agent-watcher.timer
```

Laden Sie systemd neu:

```bash
sudo systemctl daemon-reload
```

Entfernen Sie die Agent-Installation:

```bash
sudo rm -rf \
    /opt/lums-agent
```

Entfernen Sie die Client-Konfiguration:

```bash
sudo rm -f \
    /etc/default/lums-agent
```

Führen Sie diese Schritte nur durch, wenn der Client tatsächlich aus der LUMS-Verwaltung entfernt wird.

---

# 166. Abschließende Server-Installationscheckliste

Eine abgeschlossene LUMS-Installation sollte alle folgenden Punkte erfüllen:

```text
SERVER
[ ] Debian/Linux host prepared
[ ] Docker installed
[ ] Nginx installed
[ ] Repository deployed
[ ] Application secret generated
[ ] TLS material installed
[ ] LUMS image built
[ ] Persistent volume created
[ ] Hardened container deployed
[ ] Container runs as non-root
[ ] Root filesystem is read-only
[ ] Linux capabilities dropped
[ ] no-new-privileges enabled
[ ] Secret mounted read-only
[ ] Persistent data volume mounted
[ ] Application bound to 127.0.0.1:5050
[ ] Nginx HTTPS configured
[ ] HTTP redirects to HTTPS
[ ] TLS verified
[ ] Database initialized
[ ] SQLite integrity check passes
[ ] Migrations complete
```

---

# 167. Abschließende Client-Installationscheckliste

```text
CLIENT
[ ] Supported Linux distribution
[ ] systemd available
[ ] Agent installed
[ ] Agent version verified
[ ] Watcher installed
[ ] Watcher version verified
[ ] Client configuration protected
[ ] Unique client token configured
[ ] TLS trust configured
[ ] Agent manual run succeeds
[ ] Initial report accepted
[ ] Client visible in LUMS
[ ] Reporting timer enabled
[ ] Watcher timer enabled
[ ] Idle detection verified
[ ] Package inventory verified
[ ] Update detection verified
```

---

# 168. Abschließende Funktionscheckliste

```text
FUNCTIONALITY
[ ] Administrator login works
[ ] Operator login works
[ ] Viewer login works
[ ] Administrator RBAC verified
[ ] Operator RBAC verified
[ ] Viewer RBAC verified
[ ] Client authentication verified
[ ] Token rotation verified
[ ] Package search verified
[ ] Package installation verified
[ ] Package removal verified
[ ] Package update verified
[ ] System update path verified
[ ] Update jobs verified
[ ] Job result validation verified
[ ] Job recovery verified
[ ] Reboot detection verified
[ ] Audit logging verified
[ ] Logs contain no secrets
[ ] End-to-end reporting verified
[ ] End-to-end update execution verified
```

---

# 169. Abschließende Sicherheitscheckliste

```text
SECURITY
[ ] HTTPS enforced
[ ] Client Bearer authentication enabled
[ ] RBAC enforced server-side
[ ] CSRF protection enabled
[ ] Session protection enabled
[ ] Login rate limiting enabled
[ ] Password hashing enabled
[ ] Client token hashing enabled
[ ] Client token rotation available
[ ] Audit logging enabled
[ ] Secrets outside Git
[ ] Secrets outside Docker image
[ ] TLS private key protected
[ ] Docker root filesystem read-only
[ ] Linux capabilities dropped
[ ] no-new-privileges enabled
[ ] Container runs as non-root
[ ] Persistent data isolated in volume
[ ] Application port localhost-only
[ ] Firewall reviewed
[ ] Default Nginx site removed or controlled
[ ] Backup procedure defined
[ ] Restore procedure tested
```

---

# 170. Abschließende Testcheckliste

Führen Sie die vollständige automatisierte Testsuite aus:

```bash
cd /opt/lums-public

./.venv-test/bin/pytest -q
```

Die Installation sollte erst als abgeschlossen betrachtet werden, wenn die vollständige Testsuite besteht.

Prüfen Sie dann die Produktionslaufzeit manuell:

```bash
sudo docker ps \
    --filter name=lums
```

```bash
sudo docker logs \
    --tail 100 \
    lums
```

```bash
curl -I \
    https://LUMS-SERVER/
```

```bash
sudo ss -lntp
```

---

# 171. Abschließende Dokumentationsprüfung

Bevor Sie die Installation als abgeschlossen erklären, prüfen Sie, dass die Dokumentation zur tatsächlichen Bereitstellung passt.

Überprüfen Sie mindestens:

```text
install.md
security.md
troubleshooting.md
administration.md
docs/README.md
```

Die englischen Anleitungen auf Root-Ebene sind die technische Referenz. Die Übersetzungen in `docs/locales/` können noch nicht alle technischen Details enthalten.

Die Dokumentation darf nicht enthalten:

```text
old container commands
obsolete image names
obsolete RBAC rules
obsolete test counts
obsolete service paths
obsolete authentication mechanisms
real secrets
real client tokens
private keys
```

Wenn sich die Bereitstellung ändert, aktualisieren Sie die Dokumentation zusammen mit der Implementierung.

---

# 172. Release-Bereitschaft

Eine erfolgreiche Installation bedeutet nicht automatisch, dass LUMS ein offizielles Release hat.

Der aktuelle Projektzustand trennt absichtlich:

```text
Working implementation
Security audit
Documentation review
Release preparation
Versioning
Git tag
GitHub Release
```

Ein offizielles LUMS-Release sollte erst erstellt werden, nachdem die vollständige Implementierung, das Sicherheitsreview, das Dokumentationsreview und die abschließende Validierung abgeschlossen wurden.

Bis dahin behandeln Sie das Repository als aktiv entwickeltes Projekt.

---

# 173. Betriebliche Basis

Die aktuell dokumentierte Basis ist:

```text
LUMS Server
    Docker
    Nginx
    HTTPS
    SQLite
    RBAC
    CSRF
    Audit Logging
    Hardened Container

LUMS Agent
    Version 1.7.0

LUMS Watcher
    Version 1.2.1

Database
    journal_mode=wal
    busy_timeout=5000
    synchronous=2
    foreign_keys=ON (application connections)

Container
    non-root
    read-only root filesystem
    CapDrop=ALL
    no-new-privileges
    localhost-only application port

Roles
    Administrator
    Operator
    Viewer
```

Diese Basis sollte als Referenzzustand für Fehlerbehebung und zukünftige Wartung behandelt werden.

---

# 174. Installation abgeschlossen

Die Installation ist abgeschlossen, wenn:

```text
Server
  │
  ├── HTTPS works
  ├── Authentication works
  ├── RBAC works
  ├── Database is healthy
  ├── Container is hardened
  └── Persistent storage is verified
       │
       ▼
Client
  │
  ├── Agent reports
  ├── Watcher executes
  ├── Package manager works
  ├── Jobs complete
  ├── Results are validated
  └── Recovery works
       │
       ▼
Operations
  │
  ├── Backup exists
  ├── Restore is understood
  ├── Troubleshooting documentation is available
  └── Security baseline is maintained
```

Das fundamentale LUMS-Betriebsprinzip ist:

```text
Observe first.
Change second.
Verify third.
Document last.
```

Erweitern Sie dies für Produktionsänderungen zu:

```text
Backup
   ↓
Change
   ↓
Verify
   ↓
Document
```

Eine LUMS-Installation sollte immer reproduzierbar, auditierbar und wiederherstellbar bleiben.
