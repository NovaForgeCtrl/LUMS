# LUMS Fehlerbehebung

Dieses Handbuch bietet Fehlerbehebungsverfahren für den LUMS-Server, Linux-Agenten, Execution Watcher, Update-Jobs, Authentifizierung, Paketverwaltung, Datenbank und Docker-Bereitstellung.

Der Fehlerbehebungsprozess sollte immer mit **Beobachtung vor Änderung** beginnen.

Das Ziel ist es, die erste Komponente zu identifizieren, bei der das erwartete Verhalten aufhört, ohne unnötig Konfiguration, Datenbankzustand, Anmeldeinformationen oder Sicherheitskontrollen zu verändern.

---

## Erste Schritte: Sicher Fehler beheben

Wenn Sie neu in Linux sind: Ein Fehler bedeutet nicht automatisch, dass Daten verloren gegangen sind. Ändern Sie nicht mehrere Dinge gleichzeitig. Beginnen Sie mit den unten stehenden Prüfungen und notieren Sie **wann** das Problem auftritt und **welche Aktion** unmittelbar davor stattgefunden hat.

### Erste Prüfungen auf dem LUMS-Server

```bash
sudo docker ps -a --filter name=lums
sudo docker logs --tail 100 lums
sudo systemctl status nginx --no-pager
sudo nginx -t
```

`docker ps -a` zeigt auch gestoppte Container. `docker logs` liest aktuelle Anwendungsmeldungen. `systemctl status` zeigt, ob Nginx läuft; `nginx -t` prüft seine Konfiguration, ohne sie zu ändern. Wenn `nginx -t` fehlschlägt, laden Sie Nginx **nicht** neu, bis die Ursache behoben wurde.

### Erste Prüfungen auf einem verwalteten Client

```bash
sudo systemctl status lums-agent.service --no-pager
sudo journalctl -u lums-agent.service -n 100 --no-pager
sudo systemctl status lums-agent-watcher.service --no-pager
sudo journalctl -u lums-agent-watcher.service -n 100 --no-pager
```

Agent und Watcher sind separate Dienste: ein erfolgreicher Agent-Bericht beweist nicht, dass der Watcher Update-Jobs ausführen kann. Bei einem `oneshot`-Dienst kann `inactive` nach einem erfolgreichen Lauf normal sein; prüfen Sie auch das Ergebnis und die Log-Meldungen.

### Bevor Sie Befehlsausgaben teilen

Prüfen Sie Logs und Konfiguration auf Passwörter, Client-Tokens, Session- oder API-Schlüssel, private Schlüssel und persönliche Informationen. Teilen Sie niemals Secret-Dateiinhalte oder vollständige Umgebungsvariablenwerte. Wenn Sie Hilfe benötigen, teilen Sie nur die relevanten Fehlermeldungen nach Entfernung sensibler Informationen.

**Beginnen Sie nicht mit** dem Löschen der Datenbank oder des Docker-Volumes, dem Ausführen des Containers als privilegiert, dem Deaktivieren von Sicherheitsoptionen, dem Entfernen von Paketmanager-Lockdateien oder dem Rotieren von Tokens. Diese Aktionen können Daten beschädigen, Beweise löschen oder das Problem verschlimmern. Wenn eine Prüfung fehlschlägt, speichern Sie ihre Ausgabe und fahren Sie mit dem relevanten Abschnitt unten fort.

---

# 1. Fehlerbehebungsphilosophie

LUMS besteht aus mehreren unabhängigen Komponenten.

Ein erfolgreicher Client-Bericht bedeutet nicht automatisch, dass die Update-Ausführung funktioniert.

Der wichtigste operative Pfad ist:

```text
Linux Client
    │
    ├── LUMS Agent
    │
    └── Execution Watcher
            │
            ▼
          HTTPS
            │
            ▼
        Nginx
            │
            ▼
        LUMS API
            │
            ▼
         SQLite
```

Die Update-Ausführung fügt die Paketverwaltungsschicht hinzu:

```text
Browser
   │
   ▼
LUMS API
   │
   ▼
SQLite
   │
   ▼
Update Job
   │
   ▼
Execution Watcher
   │
   ▼
LUMS Agent
   │
   ▼
APT / pacman
   │
   ▼
Result
   │
   ▼
LUMS API
   │
   ▼
SQLite
```

Identifizieren Sie bei der Fehlerbehebung die **erste fehlschlagende Komponente**.

Zum Beispiel:

```text
Agent report fails
    ↓
Check agent service
    ↓
Check network
    ↓
Check TLS
    ↓
Check client token
    ↓
Check LUMS API
```

Führen Sie nicht sofort Folgendes aus:

* die Datenbank ändern
* das Docker-Volume löschen
* den Agent neu installieren
* Anmeldeinformationen rotieren
* Paketmanager-Lockdateien entfernen
* Sicherheitskontrollen deaktivieren
* den Container privilegiert machen

Diese Aktionen können nützliche Diagnoseinformationen zerstören oder zusätzliche Probleme schaffen.

---

# 2. Diagnosebasis

Bevor Sie ein bestimmtes Problem untersuchen, stellen Sie den aktuellen Zustand der Hauptkomponenten fest.

Die LUMS-Produktionsbereitstellung verwendet:

```text
Application port: 127.0.0.1:5050
External access: HTTPS through Nginx
Database: /var/lib/lums/lums.db
Docker volume: lums-data
Agent: 1.7.0
Watcher: 1.2.1
```

Der Produktionscontainer ist gehärtet mit:

```text
Read-only root filesystem
No Linux capabilities
no-new-privileges
Non-root application user
Protected secret mount
Dedicated persistent data volume
```

Der Anwendungsport ist absichtlich nur an den lokalen Host gebunden.

Der erwartete Netzwerkpfad ist:

```text
Client / Browser
       │
       ▼
     HTTPS
       │
       ▼
    Nginx :443
       │
       ▼
127.0.0.1:5050
       │
       ▼
 Docker container
       │
       ▼
    LUMS :5000
```

---

# 3. Erste Diagnoseprüfungen

## 3.1 Den LUMS-Container prüfen

Auf dem LUMS-Server:

```bash
sudo docker ps
```

Der Container `lums` sollte laufen.

Für eine vollständige Containerübersicht:

```bash
sudo docker ps -a \
    --filter name=lums
```

Entfernen Sie gestoppte Container nicht, bevor Sie sie untersucht haben.

Ältere Fallback-Container können bei der Untersuchung eines Bereitstellungsproblems nützliche Informationen enthalten.

---

## 3.2 Die aktuellen Anwendungslogs prüfen

Inspizieren Sie die neuesten LUMS-Logs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Für Live-Ausgabe:

```bash
sudo docker logs \
    -f \
    lums
```

Wenn Sie eine bestimmte Anfrage oder einen Job untersuchen, starten Sie die Log-Inspektion nach Möglichkeit, bevor Sie das Problem reproduzieren.

Dies erleichtert die Korrelation der Client-Aktion mit dem entsprechenden serverseitigen Ereignis.

---

## 3.3 Nginx prüfen

Prüfen Sie den Reverse-Proxy:

```bash
sudo systemctl status nginx \
    --no-pager
```

Validieren Sie die Konfiguration:

```bash
sudo nginx -t
```

Ein erfolgreicher Konfigurationstest sollte melden:

```text
syntax is ok
test is successful
```

Wenn Nginx nicht läuft, schlägt der HTTPS-Zugriff auf LUMS normalerweise fehl, selbst wenn der Docker-Container selbst gesund ist.

---

## 3.4 Den Agent prüfen

Auf einem verwalteten Linux-Client:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Inspizieren Sie die aktuelle Agent-Ausgabe:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Für einen Dienst mit `Type=oneshot` kann ein inaktiver Zustand nach einer erfolgreichen Ausführung normal sein.

Die wichtige Information ist das Ausführungsergebnis.

Eine erfolgreiche Ausführung sollte enden mit:

```text
status=0/SUCCESS
```

---

## 3.5 Den Execution Watcher prüfen

Der Watcher ist eine vom Berichterstattungs-Agent getrennte Komponente.

Prüfen Sie ihn unabhängig:

```bash
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Inspizieren Sie die aktuelle Ausgabe:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 100 \
    --no-pager
```

Ein erfolgreicher Agent-Bericht beweist daher **nicht**, dass der Execution Watcher korrekt funktioniert.

---

## 3.6 LUMS-Timer prüfen

Prüfen Sie alle relevanten Timer:

```bash
sudo systemctl list-timers \
    --all | grep lums
```

Die erwarteten Timer umfassen die Planungsmechanismen für Agent und Watcher.

Wenn ein Timer fehlt oder inaktiv ist, inspizieren Sie die entsprechende Unit, bevor Sie etwas ändern.

---

# 4. LUMS-Container läuft nicht

Wenn der Container `lums` nicht läuft, erstellen Sie ihn nicht sofort neu.

Inspizieren Sie zuerst seinen Zustand:

```bash
sudo docker ps -a \
    --filter name=lums
```

Inspizieren Sie dann den Container:

```bash
sudo docker inspect lums
```

Prüfen Sie die aktuellen Logs:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Prüfen Sie den Exit-Zustand:

```bash
sudo docker inspect \
    --format '{{.State.Status}} {{.State.ExitCode}}' \
    lums
```

Das Ergebnis kann helfen, zu unterscheiden zwischen:

```text
Normal shutdown
Application failure
Configuration failure
Container runtime failure
Health/startup problem
```

Wenn der Container unerwartet beendet wurde, bewahren Sie die Logs und den Containerzustand auf, bevor Sie ihn ersetzen.

---

# 5. Container startet, aber LUMS ist nicht erreichbar

Die LUMS-Anwendung ist nicht dafür vorgesehen, direkt über den Docker-Anwendungsport vom Netzwerk aus zugegriffen zu werden.

Die Produktionsanwendung ist gebunden an:

```text
127.0.0.1:5050
```

Prüfen Sie die Port-Bindung:

```bash
sudo docker port lums
```

Prüfen Sie auch die Host-Listener:

```bash
sudo ss -lntp | grep -E ':443|:5050'
```

Die erwartete Architektur ist:

```text
HTTPS :443
    │
    ▼
  Nginx
    │
    ▼
127.0.0.1:5050
    │
    ▼
Docker
    │
    ▼
LUMS :5000
```

Wenn der Container läuft, aber HTTPS fehlschlägt, untersuchen Sie die Schichten einzeln:

1. Docker-Container
2. Lokaler Anwendungsport
3. Nginx-Konfiguration
4. TLS
5. Firewall/Netzwerkpfad

Setzen Sie Port `5050` nicht als Fehlerbehebungs-Abkürzung öffentlich aus.

---

# 6. Nginx gibt einen Fehler zurück

Prüfen Sie den Dienst:

```bash
sudo systemctl status nginx \
    --no-pager
```

Validieren Sie die Konfiguration:

```bash
sudo nginx -t
```

Inspizieren Sie aktuelle Nginx-Meldungen:

```bash
sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
```

Prüfen Sie dann, dass der LUMS-Container tatsächlich läuft:

```bash
sudo docker ps
```

Ein Reverse-Proxy-Fehler bedeutet nicht automatisch, dass die LUMS-Anwendung selbst defekt ist.

Mögliche Fehlerorte sind:

```text
Browser
   ↓
TLS
   ↓
Nginx
   ↓
127.0.0.1:5050
   ↓
Docker
   ↓
LUMS
```

Testen Sie die Schichten einzeln, anstatt mehrere Komponenten gleichzeitig zu ändern.

---

# 7. HTTPS-/TLS-Probleme

Testen Sie zuerst den HTTPS-Endpunkt:

```bash
curl -I https://LUMS-SERVER/
```

Wenn die Zertifikatsvalidierung fehlschlägt, stellen Sie fest, ob das Problem liegt in:

```text
Certificate
Certificate chain
Hostname
Trust store
Nginx configuration
Client CA configuration
```

Validieren Sie Nginx:

```bash
sudo nginx -t
```

Wenn das Zertifikat oder die TLS-Konfiguration absichtlich geändert wurde, laden Sie Nginx neu:

```bash
sudo systemctl reload nginx
```

Testen Sie dann erneut:

```bash
curl -I https://LUMS-SERVER/
```

Clients, die eine private Zertifizierungsstelle verwenden, müssen dem entsprechenden CA-Zertifikat vertrauen.

Deaktivieren Sie die TLS-Zertifikatsvalidierung nicht als dauerhaften Workaround.

Ein erfolgreicher Konnektivitätstest, der die Zertifikatsvalidierung umgeht, beweist nicht, dass die Produktions-TLS-Konfiguration korrekt ist.

---

# 8. Agent-Dienst schlägt fehl

Prüfen Sie den Dienst:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Lesen Sie das aktuelle Journal:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Starten Sie den Dienst erst erneut, nachdem Sie das vorherige Ergebnis inspiziert haben:

```bash
sudo systemctl start \
    lums-agent.service
```

Prüfen Sie dann:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

und:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Achten Sie auf:

```text
Configuration errors
Missing environment values
TLS errors
Authentication failures
API errors
Python exceptions
Package-manager errors
```

Installieren Sie den Agent nicht neu, nur weil eine einzelne Ausführung fehlgeschlagen ist.

---

# 9. Agent meldet fehlendes `LUMS_TOKEN`

Der Agent erhält seine Produktionskonfiguration normalerweise über die Umgebung seines systemd-Dienstes.

Wenn der Agent manuell aus einer Shell gestartet wird, wird die systemd-`EnvironmentFile` nicht automatisch in diese Shell geladen.

Daher:

```bash
sudo /opt/lums-agent/agent.py --version
```

kann sich anders verhalten als:

```bash
sudo systemctl start \
    lums-agent.service
```

wenn der Token ausschließlich über die systemd-Konfiguration bereitgestellt wird.

Testen Sie bei der Untersuchung von Authentifizierungsproblemen zuerst den tatsächlichen Dienst:

```bash
sudo systemctl start \
    lums-agent.service
```

Inspizieren Sie dann:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Kopieren Sie Produktionstokens nicht unnötig in Shell-Befehle.

Geben Sie niemals einen Produktionstoken in ein Diagnose-Log aus.

---

# 10. Agent kann den Server nicht erreichen

Beginnen Sie mit der Netzwerkkonnektivität:

```bash
ping LUMS-SERVER
```

Testen Sie dann HTTPS:

```bash
curl -I https://LUMS-SERVER/
```

Wenn HTTPS funktioniert, aber der Agent trotzdem fehlschlägt, untersuchen Sie:

```text
Client configuration
Client token
TLS trust
API response
Client identity
Agent version
```

Inspizieren Sie den Agent:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Inspizieren Sie gleichzeitig den Server:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Dies hilft festzustellen, ob die Anfrage LUMS überhaupt erreicht.

Wenn der Client einen Verbindungsfehler sieht und der Server keine entsprechende Anfrage zeigt, untersuchen Sie den Netzwerk- oder TLS-Pfad, bevor Sie die Anwendungskonfiguration ändern.

---

# 11. Fehlerbehebung fortsetzen

Wenn die grundlegenden Server-, Docker-, Nginx-, TLS- und Agent-Schichten funktionieren, fahren Sie fort mit:

```text
Client Authentication
Token Rotation
Update Detection
Execution Watcher
Idle Detection
Pending Jobs
```

Der nächste Abschnitt fährt mit Client-Authentifizierung und tokenbezogenen Problemen fort.

# 12. Client-Authentifizierung

LUMS verwendet client-spezifische Authentifizierung für die Agent-Kommunikation.

Wenn ein Client registriert wird, erhält der Client Anmeldeinformationen, die für die authentifizierte Kommunikation mit dem LUMS-Server verwendet werden.

Authentifizierungsfehler sollten untersucht werden, ohne den Client-Token offenzulegen.

---

## 12.1 Client wird von LUMS nicht akzeptiert

Wenn ein Agent einen Authentifizierungsfehler meldet, inspizieren Sie zuerst das Agent-Log:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Inspizieren Sie dann die Logs des LUMS-Containers:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Achten Sie auf:

```text
401 Unauthorized
403 Forbidden
Invalid client token
Unknown client
Authentication failure
```

Eine `401`-Antwort deutet in der Regel auf ein Authentifizierungsproblem hin.

Eine `403`-Antwort kann anzeigen, dass die Authentifizierung erfolgreich war, aber die angeforderte Operation nicht erlaubt ist.

Rotieren Sie den Token nicht sofort.

Stellen Sie zuerst fest, ob das Problem liegt in:

```text
Wrong token
Wrong client ID
Disabled client
Incorrect server URL
TLS problem
Malformed request
Server-side authentication failure
```

---

## 12.2 Client existiert, aber Authentifizierung schlägt fehl

Prüfen Sie, ob der Client in der LUMS-Administrationsoberfläche weiterhin existiert.

Ändern Sie den Client-Datensatz nicht allein deshalb, weil eine Agent-Anfrage fehlgeschlagen ist.

Wenn der Client existiert, vergleichen Sie die konfigurierte Client-Identität mit der vom Agent verwendeten Identität.

Der Produktionstoken selbst darf niemals in Diagnoseausgaben ausgegeben werden.

Verwenden Sie Konfigurationsmetadaten und den Dienststatus zur Fehlerbehebung, anstatt Anmeldeinformationen offenzulegen.

---

# 13. Client-Token-Rotation

Die Client-Token-Rotation macht den vorherigen Token ungültig und ersetzt ihn durch ein neues Credential.

Wenn ein Token absichtlich rotiert wurde, muss der betroffene Agent den neuen Token erhalten, bevor er sich erneut authentifizieren kann.

Die erwartete Sequenz ist:

```text
Administrator
    │
    ▼
Rotate client token
    │
    ▼
Old token becomes invalid
    │
    ▼
New token assigned to client
    │
    ▼
Agent configuration updated
    │
    ▼
Agent reports again
```

Wenn der Agent weiterhin den alten Token verwendet, schlägt die Authentifizierung fehl.

---

## 13.1 Nach der Token-Rotation

Prüfen Sie den Agent-Dienst:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Führen Sie dann den Agent über systemd aus:

```bash
sudo systemctl start \
    lums-agent.service
```

Inspizieren Sie das Ergebnis:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Wenn die Authentifizierung weiterhin fehlschlägt, inspizieren Sie die Serverlogs:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Rotieren Sie den Token nicht wiederholt.

Wiederholte Rotation kann es erschweren festzustellen, welches Credential derzeit auf dem Client bereitgestellt ist.

---

# 14. Client ist deaktiviert

Ein deaktivierter Client darf nicht als aktiver verwalteter Client behandelt werden.

Wenn ein Agent, der zu einem deaktivierten Client gehört, Kommunikation versucht, inspizieren Sie das serverseitige Authentifizierungsergebnis.

Prüfen Sie:

```text
Client identity
Client enabled state
Authentication result
Agent configuration
```

Aktivieren Sie den Client nicht erneut, nur damit ein Fehler verschwindet.

Stellen Sie zuerst fest, warum der Client deaktiviert wurde.

---

# 15. Update-Erkennung

Die Update-Erkennung besteht aus mehreren unabhängigen Schritten.

Der Agent muss:

1. die Paketmanager-Abfrage ausführen
2. das Ergebnis parsen
3. das Ergebnis an LUMS senden
4. LUMS muss das Ergebnis validieren
5. LUMS muss das Ergebnis persistieren
6. die UI muss den aktuellen Zustand anzeigen

Ein Fehler in einem beliebigen Schritt kann dazu führen, dass Update-Informationen falsch erscheinen.

Der grundlegende Ablauf ist:

```text
APT / pacman
     │
     ▼
Agent
     │
     ▼
HTTPS
     │
     ▼
LUMS API
     │
     ▼
SQLite
     │
     ▼
Web UI
```

---

## 15.1 Es werden keine Updates angezeigt

Stellen Sie zuerst fest, ob der Client tatsächlich erfolgreich berichtet hat.

Prüfen Sie:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Inspizieren Sie dann den Server:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Wenn der Agent erfolgreich abgeschlossen wurde, aber keine Updates angezeigt werden, untersuchen Sie den API- und Datenbankzustand, bevor Sie den Paketmanager ändern.

---

## 15.2 Update-Erkennung unter Debian / Ubuntu

Der Debian-Paketmanager verwendet APT.

Wenn Sie APT-bezogene Probleme untersuchen, prüfen Sie zuerst, ob APT selbst funktioniert:

```bash
sudo apt update
```

Führen Sie während der Fehlerbehebung nicht automatisch Paket-Upgrades aus.

Der Zweck dieses Tests ist festzustellen, ob Repository-Metadaten erfolgreich aktualisiert werden können.

Wenn APT Repository-, DNS-, TLS-, Signatur- oder Lock-Fehler meldet, beheben Sie das zugrunde liegende APT-Problem, bevor Sie LUMS untersuchen.

---

## 15.3 Update-Erkennung unter Arch Linux

Arch Linux verwendet `pacman`.

Prüfen Sie Repository-Metadaten:

```bash
sudo pacman -Sy
```

Verwenden Sie dies nur, wenn das Aktualisieren der Repository-Metadaten tatsächlich für die Diagnose erforderlich ist.

Kombinieren Sie kein unnötiges Systemupgrade mit einem Diagnosetest.

Inspizieren Sie bei paketbezogenen Fehlern die exakte `pacman`-Ausgabe, bevor Sie die Konfiguration ändern.

---

# 16. Verfügbare Updates unterscheiden sich zwischen LUMS und dem Client

Update-Informationen können sich zwischen zwei Beobachtungen ändern.

Zum Beispiel:

```text
Client reports updates
        ↓
Repository metadata changes
        ↓
Package is upgraded manually
        ↓
LUMS displays older information
```

Berücksichtigen Sie daher immer den Zeitstempel des letzten erfolgreichen Client-Berichts.

Eine Differenz deutet nicht automatisch auf ein Datenbankproblem hin.

Prüfen Sie:

```text
Last Agent execution
Last successful report
Package-manager state
Repository metadata
Displayed update state
```

---

# 17. Paketverwaltung

Die LUMS-Paketverwaltung ist vom installierte-Pakete-Filter getrennt, der auf der Client-Seite angezeigt wird.

Der Paketverwaltungs-Workflow ist:

```text
User
 │
 ▼
Package Search
 │
 ▼
LUMS API
 │
 ▼
Agent
 │
 ▼
APT / pacman
 │
 ▼
Search Result
 │
 ▼
LUMS API
 │
 ▼
Web UI
```

Das Installieren, Entfernen oder Aktualisieren eines Pakets verwendet den normalen LUMS-Job-Mechanismus.

Der erwartete Ausführungspfad ist:

```text
Package Action
     │
     ▼
Update Job
     │
     ▼
Execution Watcher
     │
     ▼
Agent
     │
     ▼
APT / pacman
```

---

## 17.1 Paketsuche liefert keine Ergebnisse

Prüfen Sie zuerst, ob der Agent operativ ist:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Inspizieren Sie dann das Agent-Journal:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Prüfen Sie für Debian-basierte Clients die APT-Metadaten.

Prüfen Sie für Arch-basierte Clients die pacman-Repository-Metadaten.

Gehen Sie nicht davon aus, dass ein leeres Suchergebnis bedeutet, dass die LUMS-Datenbank leer ist.

Die Suche wird über den Paketmanager des Clients durchgeführt.

---

## 17.2 Paketsuche funktioniert, aber Installation schlägt fehl

Eine erfolgreiche Suche beweist nur, dass der Paketmanager das Paket finden konnte.

Sie beweist nicht, dass die Installation erfolgreich sein wird.

Mögliche Ursachen sind:

```text
Dependency conflicts
Repository changes
Package no longer available
Insufficient privileges
Package-manager lock
Disk-space problems
Network problems
Package-manager errors
```

Inspizieren Sie den entsprechenden Update-Job.

Das Agent-Journal sollte das Paketmanager-Ergebnis enthalten.

---

# 18. Paketinstallations-Jobs

Die Paketinstallation verwendet die normale Update-Job-Infrastruktur.

Die relevante Aktion ist:

```text
INSTALL_PACKAGE
```

Bei der Fehlerbehebung einer Installation:

1. Prüfen Sie den Job-Zustand in LUMS.
2. Prüfen Sie die Agent-Ausführung.
3. Prüfen Sie die Paketmanager-Ausgabe.
4. Prüfen Sie das endgültige an LUMS gemeldete Ergebnis.

Ändern Sie den Job-Status in SQLite nicht manuell.

Der erwartete Lebenszyklus ist:

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

Eine fehlgeschlagene Paketinstallation sollte durch die normalen Job- und Audit-Mechanismen nachvollziehbar bleiben.

---

# 19. Paketentfernungs-Jobs

Die Paketentfernung folgt demselben Job-Lebenszyklus.

Die Aktion ist:

```text
REMOVE_PACKAGE
```

Wenn eine Entfernung fehlschlägt, inspizieren Sie:

```text
Update job
Agent journal
Package-manager output
Final job result
```

Entfernen Sie keine Datenbankeinträge manuell, um eine fehlgeschlagene Paketoperation zu verbergen.

Ein fehlgeschlagener Job ist nützliche Diagnoseinformation.

---

# 20. Paketupdate-Jobs

Ein paketspezifisches Update verwendet:

```text
UPDATE_PACKAGE
```

Das Paket muss LUMS als mit einem verfügbaren Update bekannt sein, bevor der Job erstellt wird.

Wenn die UI das erwartete Paketupdate nicht anbietet:

1. Update-Informationen aktualisieren
2. Paketmanager-Zustand prüfen
3. Ergebnis der verfügbaren Updates prüfen
4. Serverlogs inspizieren, wenn der Zustand inkonsistent ist

Fügen Sie keine Update-Datensätze manuell in SQLite ein.

---

# 21. Systemupdate-Jobs

Ein vollständiges Systemupdate verwendet:

```text
UPDATE_SYSTEM
```

Dies ist anders als:

```text
UPDATE_PACKAGE
```

Das Systemupdate kann mehrere Pakete betreffen und kann je nach Betriebssystem und resultierendem Paketzustand einen Reboot erfordern.

Stellen Sie bei der Fehlerbehebung eines Systemupdates fest, ob der Fehler aufgetreten ist während:

```text
Update preparation
Package-manager execution
Result collection
Reboot detection
Post-reboot reporting
```

---

# 22. Paketmanager-Sperren

Paketmanager können eine Operation verweigern, wenn bereits ein anderer Paketverwaltungsprozess läuft.

Typische Beispiele sind:

```text
APT is already running
dpkg is locked
pacman is locked
```

Identifizieren Sie zuerst den Prozess, der die Sperre hält.

Löschen Sie Lockdateien nicht blind.

Eine Lockdatei kann anzeigen, dass ein anderer Paketverwaltungsprozess legitimerweise aktiv ist.

Das Entfernen während einer laufenden Paketoperation kann den Paketverwaltungszustand beschädigen.

Die korrekte Fehlerbehebungssequenz ist:

```text
Lock error
   ↓
Identify active process
   ↓
Determine whether it is legitimate
   ↓
Wait or resolve the process safely
   ↓
Retry operation
```

---

# 23. Paketmanager-Fehler vs. LUMS-Fehler

Unterscheiden Sie immer zwischen einem Paketmanager-Fehler und einem LUMS-Fehler.

Zum Beispiel:

```text
APT fails
    ↓
Agent reports APT failure
    ↓
LUMS stores FAILED result
```

In diesem Fall kann LUMS korrekt funktionieren, obwohl der Job fehlgeschlagen ist.

Umgekehrt:

```text
APT succeeds
    ↓
Agent cannot report result
    ↓
LUMS never receives SUCCESS
```

Hier kann die Paketoperation erfolgreich gewesen sein, während der LUMS-Berichterstattungspfad fehlgeschlagen ist.

Das Paketmanager-Ergebnis und das LUMS-Job-Ergebnis müssen daher getrennt untersucht werden.

---

# 24. Nützliche Diagnosetrennung

Wenn ein Paketjob fehlschlägt, klassifizieren Sie den Fehler zuerst:

```text
A. Package-manager failure
B. Agent execution failure
C. Agent reporting failure
D. Server/API failure
E. Database persistence failure
F. UI display problem
```

Diese Klassifikation verhindert, dass unzusammenhängende Komponenten geändert werden.

Ein Paketmanager-Fehler sollte nicht automatisch zu einem Docker-Rebuild führen.

Ein UI-Anzeigeproblem sollte nicht automatisch zum Löschen der Datenbank führen.

Ein Authentifizierungsfehler sollte nicht automatisch zur Neuinstallation des Agent führen.

---

# 25. Nächster Fehlerbehebungsbereich

Wenn Client-Authentifizierung, Update-Erkennung und Paketverwaltung funktionieren, ist der nächste Diagnosebereich der Ausführungslebenszyklus selbst:

```text
Update Job
    ↓
Watcher
    ↓
Agent
    ↓
Execution
    ↓
Result
    ↓
Checkpoint / Recovery
    ↓
Final Job State
```

Der nächste Abschnitt behandelt **Execution Watcher, Idle Detection, Job State, Recovery und Reboot-Behandlung**.

# 26. Ausführung von Update-Jobs

LUMS-Update-Jobs werden asynchron über den Agent und den Execution Watcher ausgeführt.

Der normale Ausführungspfad ist:

```text
User
 │
 ▼
LUMS API
 │
 ▼
SQLite
 │
 ▼
Pending Job
 │
 ▼
Execution Watcher
 │
 ▼
Agent
 │
 ▼
Package Manager
 │
 ▼
Result
 │
 ▼
LUMS API
 │
 ▼
SQLite
```

Ein Job, der in der UI sichtbar ist, wird nicht notwendigerweise bereits ausgeführt.

Stellen Sie immer zuerst den aktuellen Job-Zustand fest.

---

## 26.1 Job bleibt in `PENDING` hängen

Wenn ein Job in `PENDING` bleibt, prüfen Sie den Execution Watcher, bevor Sie den Agent untersuchen.

Prüfen Sie den Watcher:

```bash id="wq5h3v"
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Inspizieren Sie die aktuelle Watcher-Ausgabe:

```bash id="8y0v7e"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Prüfen Sie dann den Agent:

```bash id="j8x4qm"
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Ein ausstehender Job zeigt normalerweise an, dass die Ausführungsphase noch nicht begonnen hat.

Mögliche Ursachen sind:

```text
Watcher is not running
Watcher timer is not running
Client is offline
Client is not idle
Client has not reported recently
Job is not eligible for execution yet
```

Ändern Sie den Job-Zustand nicht manuell in SQLite.

---

# 27. Job bleibt in `RUNNING` hängen

Ein `RUNNING`-Job zeigt an, dass die Ausführung begonnen hat.

Stellen Sie zuerst fest, ob der Agent den Job tatsächlich ausführt.

Prüfen Sie:

```bash id="s2z5ek"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Inspizieren Sie dann den Watcher:

```bash id="x4f6cb"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Ein laufender Job kann einige Zeit dauern, abhängig von:

```text
Package count
Repository speed
Network latency
Package-manager operations
System load
Reboot requirements
```

Beenden Sie keine aktive Paketoperation nur deshalb, weil die UI noch nicht aktualisiert wurde.

Stellen Sie zuerst fest, ob der zugrunde liegende Prozess noch aktiv ist.

---

# 28. Job ist `FAILED`

Ein fehlgeschlagener Job zeigt nicht notwendigerweise einen LUMS-Serverfehler an.

Stellen Sie fest, welche Schicht den Fehler erzeugt hat.

Inspizieren Sie:

```text id="5t9b83"
Job state
Agent execution result
Package-manager result
Server logs
Agent logs
```

Die Hauptkategorien sind:

```text
Package-manager failure
Agent execution failure
Agent reporting failure
Server/API failure
Authentication failure
Recovery failure
```

Der ursprüngliche Fehler sollte, wo immer möglich, bewahrt werden.

Ersetzen Sie einen fehlgeschlagenen Job nicht durch einen manuell erstellten Erfolgsdatensatz.

---

# 29. Job ist `SUCCESS`, aber das Paket wurde nicht geändert

Ein erfolgreicher LUMS-Job bedeutet, dass die angeforderte Operation gemäß dem Agent-Ergebnis abgeschlossen wurde.

Wenn der erwartete Paketzustand nicht zum Job-Ergebnis passt, prüfen Sie den Client direkt.

Für Debian-basierte Systeme:

```bash id="gqdbm7"
dpkg-query -W \
    -f='${Package} ${Version}\n' \
    PACKAGE_NAME
```

Für Arch Linux:

```bash id="2x9f7v"
pacman -Q \
    PACKAGE_NAME
```

Ersetzen Sie `PACKAGE_NAME` durch das zu untersuchende Paket.

Vergleichen Sie dann den lokalen Paketzustand mit dem LUMS-Ergebnis.

Mögliche Erklärungen sind:

```text
Package was changed after the job
Package name refers to a virtual/provided package
Package-manager output was interpreted differently than expected
The job result was generated before another local change
```

Ändern Sie die LUMS-Datenbank nicht, bis die Diskrepanz identifiziert wurde.

---

# 30. Execution Watcher

Der Execution Watcher ist verantwortlich für das Erkennen von Jobs, die zur Ausführung berechtigt sind.

Der Watcher muss als unabhängige Komponente behandelt werden.

Prüfen Sie seinen Dienst:

```bash id="w5m0c8"
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Prüfen Sie seinen Timer:

```bash id="3v1x7r"
sudo systemctl list-timers \
    --all | grep lums
```

Inspizieren Sie sein Journal:

```bash id="d5m0xk"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Wenn der Agent funktioniert, aber Jobs nie starten, sollte der Watcher eine der ersten zu untersuchenden Komponenten sein.

---

# 31. Watcher läuft, führt aber keine Jobs aus

Eine Watcher-Ausführung bedeutet nicht automatisch, dass ein Job gestartet wird.

Der Job muss die Ausführungsbedingungen erfüllen.

Prüfen Sie:

```text id="m7p2zq"
Client exists
Client is enabled
Client is reachable
Client has recent status
Client is eligible
Job is pending
Job is not already completed
Execution conditions are satisfied
```

Wenn der Client nicht berechtigt ist, kann der Watcher den Job korrekt ausstehend lassen.

Dies ist nicht notwendigerweise ein Fehler.

---

# 32. Idle-Erkennung

LUMS kann Client-Idle-Informationen verwenden, wenn entschieden wird, ob ein Job ausgeführt werden soll.

Der Zweck ist es, Wartungsoperationen zu vermeiden, während der Client aktiv genutzt wird.

Die Idle-Entscheidung sollte daher als Planungsbedingung behandelt werden, nicht als Ausführungsfehler.

Ein Client kann erfolgreich berichten und trotzdem als nicht-idle betrachtet werden.

Die Fehlerbehebungssequenz ist:

```text
Agent reports
     ↓
Idle information available?
     ↓
Idle state acceptable?
     ↓
Job eligible?
     ↓
Watcher executes
```

---

## 32.1 Client berichtet, wird aber nicht als idle betrachtet

Prüfen Sie das Agent-Journal:

```bash id="5r2q1k"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Achten Sie auf die gemeldeten Idle-Informationen.

Inspizieren Sie dann den Watcher:

```bash id="2a6v8m"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Die wichtige Unterscheidung ist:

```text
Agent communication successful
```

versus:

```text
Client eligible for maintenance execution
```

Dies sind getrennte Zustände.

---

# 33. Idle-Erkennung ist nicht verfügbar

Einige Systeme stellen möglicherweise nicht alle Idle-Zustandsinformationen bereit.

Ein nicht verfügbarer Idle-Mechanismus sollte nicht automatisch als defekter Agent interpretiert werden.

Stellen Sie zuerst die gemeldete Fähigkeit fest.

Die relevanten Konzepte sind:

```text
Idle supported
Idle source
Idle state
Idle duration
```

Wenn die Plattform die erwarteten Idle-Informationen nicht bereitstellen kann, untersuchen Sie die plattformspezifische Implementierung des Agent, anstatt die Serverdatenbank zu ändern.

---

# 34. Wiederherstellung von Update-Jobs

LUMS verwendet Checkpointing und Wiederherstellung, um zu verhindern, dass unterbrochene Update-Jobs als abgeschlossen behandelt werden.

Ein Job kann unterbrochen werden durch:

```text
Agent restart
Client reboot
Network interruption
Package-manager interruption
Server restart
Watcher restart
System failure
```

Die Wiederherstellung muss zwischen bereits abgeschlossener Arbeit und noch auszuführender Arbeit unterscheiden.

Das Prinzip ist:

```text
Completed work remains completed.
Incomplete work remains recoverable.
```

---

# 35. Unterbrochener Job

Wenn ein Job unterbrochen wurde, inspizieren Sie zuerst seinen Zustand.

Inspizieren Sie dann den Agent:

```bash id="3u8d4k"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Inspizieren Sie den Watcher:

```bash id="w4x1b9"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Markieren Sie den Job nicht manuell als erfolgreich.

Der Wiederherstellungsmechanismus sollte feststellen, welche Paket-Elemente bereits abgeschlossen wurden.

---

# 36. Wiederherstellung wiederholt eine Paketoperation

Wenn die Wiederherstellung ausgelöst wird, sollten bereits erfolgreiche Paket-Elemente nicht unnötig erneut ausgeführt werden.

Das Wiederherstellungsmodell basiert auf Element-Level-Zustand.

Konzeptionell:

```text
Job
 ├── Package A → SUCCESS
 ├── Package B → SUCCESS
 ├── Package C → FAILED
 └── Package D → PENDING
```

Die Wiederherstellung sollte die erfolgreichen Elemente bewahren und mit der verbleibenden Arbeit fortfahren.

Wenn dieses Verhalten falsch erscheint, inspizieren Sie den Job- und Paket-Element-Verlauf, bevor Sie die Datenbank ändern.

---

# 37. Client bootet während eines Updates neu

Ein Reboot kann den Agent-Prozess unterbrechen.

Der erwartete Wiederherstellungspfad ist:

```text
Update starts
    ↓
Package operation
    ↓
Client reboot
    ↓
Agent starts again
    ↓
State is reported
    ↓
LUMS evaluates recovery
```

Ein Reboot bedeutet daher nicht automatisch, dass der Job dauerhaft fehlgeschlagen ist.

Inspizieren Sie den Agent-Dienst, nachdem der Client zurückkehrt:

```bash id="jjh3u8"
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Inspizieren Sie dann aktuelle Ausführungen:

```bash id="h7y5gk"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

---

# 38. Reboot-Erkennung

Die Reboot-Erkennung wird verwendet, um festzustellen, ob ein System-Reboot als Teil einer Update-Operation aufgetreten ist.

Dies ist besonders relevant, wenn ein Update Pakete ändert, die einen Neustart oder Reboot erfordern.

Für Arch Linux darf die Reboot-Erkennung nicht mit dem Exit-Status des Paketmanagers verwechselt werden.

Eine Paketoperation kann erfolgreich sein, während das System noch einen Reboot erfordert.

Vergleichen Sie bei der Fehlerbehebung der Reboot-Behandlung:

```text
Package operation result
Reboot requirement
Actual reboot state
Post-reboot Agent report
Final LUMS job state
```

---

# 39. Job-Ergebnis wurde nicht berichtet

Wenn die Paketoperation abgeschlossen zu sein scheint, aber LUMS das Endergebnis nicht anzeigt, untersuchen Sie den Berichterstattungspfad.

Prüfen Sie den Agent:

```bash id="t0r8kf"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Prüfen Sie dann den Server:

```bash id="h5n1xv"
sudo docker logs \
    --tail 200 \
    lums
```

Wenn der Agent einen Fehler meldet, während die Paketoperation selbst erfolgreich war, klassifizieren Sie das Problem als Berichterstattungsfehler und nicht als Paketverwaltungsfehler.

---

# 40. Server-Neustart während der Job-Ausführung

Ein Server-Neustart darf nicht automatisch als Beweis dafür behandelt werden, dass eine Update-Operation fehlgeschlagen ist.

Der Job-Zustand muss ausgewertet werden, nachdem der Server wieder verfügbar ist.

Prüfen Sie:

```text id="j4t7yw"
Container state
Database availability
Job state
Client state
Agent report
Watcher state
```

Der Wiederherstellungsmechanismus ist dafür verantwortlich festzustellen, ob unterbrochene Arbeit sicher fortgesetzt werden kann.

Schreiben Sie Job-Zustände nach einem Server-Neustart nicht manuell um.

---

# 41. Datenbank ist verfügbar, aber Job-Zustand sieht falsch aus

Wenn SQLite zugänglich ist, aber der Job-Zustand inkonsistent erscheint, inspizieren Sie die Anwendungs- und Audit-Logs, bevor Sie die Datenbank ändern.

Nützliche Informationen umfassen:

```text
Job ID
Client ID
Job action
Job creation time
Current state
Package-item states
Agent result
Recovery events
Audit events
```

Die Datenbank ist ein Anwendungsdatenspeicher, keine manuelle Reparatur-Schnittstelle.

Direkte Änderungen können Validierung, Autorisierung, Auditierung und Wiederherstellungslogik umgehen.

---

# 42. Manuelle Job-Zustandsänderungen

Manuelle SQL-Änderungen am Update-Job-Zustand sollten nicht als normale Fehlerbehebung verwendet werden.

Vermeiden Sie Operationen wie:

```sql id="8hbyqv"
UPDATE update_jobs ...
```

oder:

```sql id="n1h7yr"
DELETE FROM update_jobs ...
```

es sei denn, ein kontrolliertes Datenbank-Wiederherstellungsverfahren verlangt sie ausdrücklich.

Wenn eine Reparatur auf Datenbankebene wirklich erforderlich ist, bewahren Sie ein Backup auf und dokumentieren Sie die genaue Änderung, bevor Sie sie anwenden.

Normale operative Probleme sollten über die Anwendungs- und Agent-Mechanismen gelöst werden.

---

# 43. Watcher- und Agent-Diagnosematrix

Verwenden Sie die folgende Matrix, um die wahrscheinlichste Schicht zu identifizieren:

| Symptom                                                | Zuerst zu prüfende Komponente |
| ------------------------------------------------------ | ----------------------------- |
| Client kann sich nicht authentifizieren                | Agent + LUMS API              |
| Client berichtet erfolgreich, aber Job bleibt ausstehend | Execution Watcher           |
| Job wechselt zu Running, endet aber nicht              | Agent + Paketmanager          |
| Paketoperation schlägt fehl                            | Paketmanager                  |
| Paketoperation erfolgreich, aber Ergebnis fehlt        | Agent-Berichterstattung       |
| Client während Update neu gebootet                     | Agent + Wiederherstellung     |
| Job nach Neustart inkonsistent                         | Wiederherstellung + DB-Zustand |
| Job wird nie entdeckt                                  | Watcher + Timer               |
| Client ist nicht berechtigt                            | Idle / Client-Zustand         |
| UI zeigt veralteten Zustand                            | API + letzter Client-Bericht  |

Diese Matrix ist ein Ausgangspunkt, kein Ersatz für die Inspektion der tatsächlichen Logs und des Job-Zustands.

---

# 44. Nächster Fehlerbehebungsbereich

Nach der Verifikation der Job-Ausführung sind die nächsten Bereiche:

```text
SQLite and database state
RBAC and user management
Authentication sessions
Application and audit logging
Container security
Tests and CI
```

Diese Bereiche sollten getrennt von der Paketausführung untersucht werden.

# 45. SQLite- und Datenbank-Fehlerbehebung

LUMS verwendet SQLite als Anwendungsdatenbank.

Die Produktionsdatenbank wird im persistenten Docker-Volume gespeichert:

```text id="9c6w3e"
/var/lib/lums/lums.db
```

Die Datenbank wird von der Anwendung verwaltet und darf normalerweise nicht manuell geändert werden.

Stellen Sie bei der Untersuchung datenbankbezogener Probleme zuerst fest, ob das Problem liegt in:

```text id="4k4z1m"
Database availability
Database locking
Application configuration
Data consistency
Migration state
Application logic
```

---

# 46. Datenbank ist nicht verfügbar

Wenn LUMS einen Datenbankfehler meldet, prüfen Sie zuerst, ob der Container läuft:

```bash id="0l5q6h"
sudo docker ps
```

Inspizieren Sie dann die Anwendungslogs:

```bash id="6j5p8m"
sudo docker logs \
    --tail 200 \
    lums
```

Löschen Sie nicht sofort das Docker-Volume.

Das persistente Volume enthält die Produktionsanwendungsdaten.

Das Löschen kann dauerhaft entfernen:

```text id="4bq9rj"
Users
Clients
Client configuration
Update jobs
Audit data
Application state
```

---

# 47. SQLite-Datenbanksperrung

SQLite-Sperrprobleme sollten über die Anwendungslogs untersucht werden.

Inspizieren Sie:

```bash id="l8f6vk"
sudo docker logs \
    --tail 200 \
    lums
```

Die Produktionsanwendung verwendet:

```text id="2d3m8x"
journal_mode = wal
busy_timeout = 5000
synchronous = 2
```

Die Anwendung aktiviert außerdem die SQLite-Fremdschlüssel-Durchsetzung für ihre Datenbankverbindungen.

Eine Datenbanksperre bedeutet nicht automatisch, dass die Datenbank beschädigt ist.

Mögliche Ursachen sind:

```text id="9w4qcz"
Concurrent writes
Long-running transaction
Application process still using the database
Unexpected process termination
Filesystem problem
```

Löschen Sie SQLite-Journal-Dateien nicht manuell.

---

# 48. SQLite-Fremdschlüssel

LUMS aktiviert ausdrücklich die SQLite-Fremdschlüssel-Durchsetzung auf Anwendungsebene.

Dies bedeutet, dass Beziehungen zwischen Datenbankdatensätzen von SQLite validiert werden, wenn die Anwendungsverbindung hergestellt wird.

Wenn ein fremdschlüsselbezogener Fehler auftritt, inspizieren Sie zuerst die Anwendungslogs.

Deaktivieren Sie die Fremdschlüssel-Durchsetzung nicht, um eine Operation erfolgreich zu machen.

Ein Fremdschlüsselfehler kann auf ein Anwendungslogik- oder Datenintegritätsproblem hinweisen.

---

# 49. SQLite-Datenbankintegrität

Wenn Datenbankbeschädigung vermutet wird, stellen Sie zuerst unnötige Änderungen ein.

Bewahren Sie den aktuellen Zustand auf und inspizieren Sie die Anwendungslogs.

Eine kontrollierte Integritätsprüfung kann gegen eine Kopie der Datenbank durchgeführt werden.

Führen Sie keine destruktiven Reparaturvorgänge direkt gegen die Produktionsdatenbank durch, es sei denn, ein dokumentiertes Wiederherstellungsverfahren verlangt dies.

Das allgemeine Prinzip ist:

```text id="t4d1km"
Preserve
   ↓
Inspect
   ↓
Verify
   ↓
Recover
   ↓
Validate
```

Beginnen Sie niemals mit:

```text id="z1f6rw"
Delete database
Recreate database
Recreate Docker volume
```

---

# 50. Datenbankmigrationen

LUMS verwendet Anwendungsmigrationen, um Datenbankschemaänderungen einzuführen.

Wenn ein Migrationsproblem auftritt, inspizieren Sie die Containerlogs:

```bash id="x4h9vf"
sudo docker logs \
    --tail 200 \
    lums
```

Achten Sie auf:

```text id="m2x7kc"
Migration failure
SQL error
Duplicate column
Missing table
Constraint error
Migration already applied
```

Bearbeiten Sie Migrationsdatensätze nicht manuell, es sei denn, das Migrationssystem verlangt ausdrücklich ein kontrolliertes Wiederherstellungsverfahren.

Eine Migration, die bereits angewendet wurde, sollte normalerweise nicht manuell erneut ausgeführt werden.

---

# 51. Datenbank-Volume

Die LUMS-Datenbank wird im persistenten Docker-Volume gespeichert:

```text id="p6m3jw"
lums-data
```

Inspizieren Sie das Volume:

```bash id="v4c7yq"
sudo docker volume inspect \
    lums-data
```

Das Volume muss über die normale Container-Neuerstellung hinweg persistent bleiben.

Der Anwendungscontainer selbst ist wegwerfbar.

Die Anwendungsdaten nicht.

Daher:

```text id="z9f4ws"
Container
    ≠
Persistent database
```

Das Neuerstellen des Containers darf nicht mit dem Neuerstellen des Daten-Volumes verwechselt werden.

---

# 52. Datenbank-Festplattenplatz

SQLite benötigt verfügbaren Dateisystemplatz für den normalen Betrieb.

Prüfen Sie das Host-Dateisystem:

```bash id="j6k1pt"
df -h
```

Prüfen Sie auch die Inode-Verfügbarkeit:

```bash id="q2c5ra"
df -i
```

Wenig Festplattenplatz kann Datenbankfehler erzeugen, die anfangs wie Anwendungsprobleme aussehen.

Wenn die Datenbank plötzlich schreibgeschützt wird oder Schreibvorgänge zu fehlschlagen beginnen, prüfen Sie die Dateisystemkapazität, bevor Sie die SQLite-Konfiguration ändern.

---

# 53. RBAC-Fehlerbehebung

LUMS verwendet rollenbasierte Zugriffskontrolle.

Die aktuellen Rollen sind:

```text id="k8w5j2"
Administrator
Operator
Viewer
```

Die Berechtigungen sind absichtlich unterschiedlich.

---

## 53.1 Administrator

Administratoren können:

```text id="n4x7pa"
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

Ausschließlich für Administratoren vorgesehene Operationen umfassen Benutzerverwaltung und Rollenadministration.

---

## 53.2 Operator

Operatoren können:

```text id="b7c2mz"
View clients
View installed software
View available updates
Create and execute update jobs
View update history
Use package management
Use system maintenance
```

Operatoren können nicht:

```text id="q8v3kd"
Manage users
Manage roles
Create or disable clients
Rotate client tokens
```

---

## 53.3 Viewer

Viewer haben absichtlich eingeschränkten Zugriff.

Ein Viewer kann:

```text id="y5m2rx"
View clients
View installed software
```

Die folgende Funktionalität ist für die Viewer-Oberfläche ausgeblendet und serverseitig blockiert:

```text id="e8c4nw"
Available Updates
Update Jobs
Update History
Package Management
System Maintenance
```

Dies ist eine beabsichtigte Sicherheitskontrolle.

Wenn ein Viewer auf eine dieser Funktionen zugreifen kann, behandeln Sie das Problem als RBAC-Problem und nicht nur als UI-Problem.

---

# 54. Viewer sieht zu viel

Wenn ein Viewer Funktionalität sieht, die nicht verfügbar sein sollte, prüfen Sie beide Schichten:

```text id="x5j3mq"
Browser UI
    +
Server-side authorization
```

Das Ausblenden eines Elements in JavaScript oder HTML ist keine ausreichende Sicherheit.

Die API muss nicht autorisierte Operationen ebenfalls ablehnen.

Bei der Untersuchung:

1. Stellen Sie die Rolle des authentifizierten Benutzers fest.
2. Identifizieren Sie den betroffenen Endpunkt.
3. Prüfen Sie die Serverantwort.
4. Inspizieren Sie bei Bedarf die Anwendungslogs.
5. Verifizieren Sie den relevanten RBAC-Test.

Lösen Sie ein Autorisierungsproblem nicht nur durch Ausblenden des UI-Elements.

---

# 55. Viewer kann erwartete Daten nicht sehen

Ein Viewer sollte weiterhin auf die Informationen zugreifen können, die durch das aktuelle RBAC-Modell ausdrücklich erlaubt sind.

Wenn erlaubte Client-Informationen fehlen:

```text id="3h6q8f"
Verify login
   ↓
Verify role
   ↓
Verify client visibility
   ↓
Inspect API response
   ↓
Inspect browser console if necessary
```

Gewähren Sie keine zusätzlichen Berechtigungen, nur weil eine Seite derzeit unvollständig erscheint.

Stellen Sie zuerst fest, ob die fehlenden Informationen absichtlich eingeschränkt sind.

---

# 56. Operator kann eine Operation nicht durchführen

Wenn ein Operator `403 Forbidden` erhält, stellen Sie zuerst fest, ob die angeforderte Aktion ausschließlich für Administratoren vorgesehen ist.

Operatorzugriff umfasst nicht:

```text id="n5y7cu"
User management
Role administration
Client creation/deactivation
Client token rotation
```

Wenn die Operation für Operatoren erlaubt sein sollte, inspizieren Sie den Autorisierungsdekorator des Endpunkts und die entsprechenden RBAC-Tests.

Befördern Sie den Benutzer nicht vorübergehend zum Administrator als Diagnose-Abkürzung.

---

# 57. Administrator kann eine Operation nicht durchführen

Ein Administrator sollte Zugriff auf alle derzeit unterstützten administrativen Operationen haben.

Wenn ein Administrator einen Autorisierungsfehler erhält:

```text id="q7d2nv"
Verify authenticated session
        ↓
Verify current role
        ↓
Verify endpoint authorization
        ↓
Inspect CSRF requirements
        ↓
Inspect application logs
```

Für zustandsändernde Operationen kann eine gültige Sitzung allein nicht ausreichend sein.

Der CSRF-Schutz muss, wo erforderlich, ebenfalls erfüllt sein.

---

# 58. Benutzerverwaltung

Die Benutzerverwaltung ist auf Administratoren beschränkt.

Der Benutzerverwaltungs-Workflow ist:

```text id="x4j6pw"
Administrator
    │
    ▼
User Management
    │
    ├── Create user
    ├── Assign role
    └── Enable / disable user
```

Wenn ein Benutzer nicht erstellt werden kann, prüfen Sie:

```text id="b3q9fz"
Current role
Username validation
Role validation
Duplicate username
Password validation
CSRF protection
Application logs
```

Erstellen Sie Benutzer nicht direkt in SQLite.

Direkte Datenbankeinfügung umgeht Passwort-Hashing, Validierung, Autorisierung und Audit-Logging.

---

# 59. Benutzererstellung schlägt fehl

Wenn die Benutzererstellung fehlschlägt, inspizieren Sie die Browserantwort und die Serverlogs.

Die API sollte validieren:

```text id="7x3m5n"
Username
Role
Password requirements
Duplicate account
Authenticated administrator
CSRF token
```

Wenn die Anfrage abgelehnt wird, stellen Sie fest, welche Validierungsregel ausgelöst wurde.

Schwächen Sie die Validierung nicht, nur damit eine einzelne Kontoerstellungsanfrage erfolgreich ist.

---

# 60. Passwortprobleme

LUMS speichert Benutzerpasswörter mit einem Passwort-Hashing-Mechanismus statt Klartextpasswörtern.

Wenn ein Benutzer sich nicht anmelden kann:

```text id="9w3r5b"
Verify username
   ↓
Verify account enabled state
   ↓
Verify password
   ↓
Check login rate limiting
   ↓
Inspect authentication logs
```

Speichern oder loggen Sie niemals Klartextpasswörter.

Kopieren Sie Passwörter nicht in Diagnosebefehle oder Logdateien.

---

# 61. Deaktiviertes Benutzerkonto

Ein deaktiviertes Konto darf nicht als aktives Login-Konto behandelt werden.

Wenn sich ein deaktivierter Benutzer weiterhin authentifizieren kann, untersuchen Sie:

```text id="z6t2hx"
Current account state
Authentication lookup
Session state
Session revocation
Browser session
Server-side authorization
```

Löschen Sie das Konto nicht einfach.

Die Bewahrung des Kontos kann für den Audit-Verlauf wichtig sein.

---

# 62. Sitzungsprobleme

LUMS verwendet serverseitige Sitzungsverwaltung.

Wenn ein Benutzer veralteten oder unerwarteten Zugriff zu haben scheint, melden Sie sich zuerst ab und stellen Sie eine frische Sitzung her.

Wenn das Problem fortbesteht, untersuchen Sie:

```text id="q1y7vm"
Account state
Role
Session state
Session revocation
Cookie configuration
CSRF protection
```

Deaktivieren Sie keine Sitzungssicherheitskontrollen, um ein Login-Problem zu umgehen.

---

# 63. Sitzungswiderruf

Der Sitzungswiderruf ist relevant, wenn:

```text id="4n8z7p"
A password changes
A user is disabled
A role changes
A session must be invalidated
A security event requires forced logout
```

Wenn ein Benutzer nach einer Kontoänderung weiterhin Zugriff zu haben scheint, stellen Sie fest, ob die bestehende Sitzung korrekt invalidiert wurde.

Testen Sie mit einer frischen Browsersitzung erst, nachdem Sie den Kontozustand bestätigt haben.

Gehen Sie nicht davon aus, dass das Löschen von Browser-Cookies allein beweist, dass der serverseitige Sitzungswiderruf funktioniert.

---

# 64. Login-Ratenbegrenzung

LUMS wendet Login-Ratenbegrenzung auf wiederholte fehlgeschlagene Authentifizierungsversuche an.

Das aktuelle Verhalten verwendet zunehmende Sperrintervalle:

```text id="p7k4xz"
5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

Der Fehlerzustand wird in SQLite persistiert.

Wenn Login-Versuche unerwartet blockiert werden, inspizieren Sie den Authentifizierungszustand, bevor Sie die Datenbank ändern.

Eine Rate-Limit-Antwort ist nicht automatisch ein Authentifizierungsfehler.

Sie kann anzeigen, dass das Konto den konfigurierten Fehlversuchs-Schwellenwert erreicht hat.

---

# 65. Login funktioniert, aber API gibt `403` zurück

Ein erfolgreicher Login beweist Authentifizierung, nicht Autorisierung.

Eine `403 Forbidden`-Antwort kann anzeigen:

```text id="m9c2vx"
Insufficient role
Missing CSRF protection
Disallowed operation
Disabled functionality
```

Identifizieren Sie den genauen Endpunkt, bevor Sie etwas ändern.

Die korrekte Fehlerbehebungsfrage ist:

```text id="0q4g1k"
"Is this user authenticated?"
```

gefolgt von:

```text id="x8v5md"
"Is this authenticated user authorized for this operation?"
```

Dies sind getrennte Sicherheitsprüfungen.

---

# 66. CSRF-Fehler

Zustandsändernde Browser-Anfragen sind gegen Cross-Site Request Forgery geschützt.

Wenn eine zustandsändernde Anfrage unerwartet fehlschlägt:

```text id="6z4qpn"
Verify authenticated session
        ↓
Verify CSRF token
        ↓
Verify request method
        ↓
Verify endpoint
        ↓
Inspect server response
```

Deaktivieren Sie den CSRF-Schutz nicht als Fehlerbehebungs-Workaround.

Eine fehlgeschlagene CSRF-Prüfung ist eine Sicherheitskontrolle, die wie vorgesehen funktioniert.

---

# 67. Browser-UI und API stimmen nicht überein

Wenn die UI anzeigt, dass eine Aktion verfügbar ist, aber die API sie ablehnt:

```text id="v8n3ty"
Browser UI
   ↓
Displayed role/state
   ↓
API request
   ↓
Server-side authorization
```

Das serverseitige Ergebnis ist maßgeblich.

Die UI kann veralteten Zustand enthalten nach:

```text id="4g7m2x"
Role changes
Session changes
Client changes
Page remains open for a long time
```

Laden Sie die Seite neu und stellen Sie eine frische Sitzung her, bevor Sie annehmen, dass die serverseitige Autorisierung falsch ist.

---

# 68. RBAC-Diagnosematrix

| Symptom                          | Zuerst zu prüfende Komponente           |
| -------------------------------- | --------------------------------------- |
| Viewer sieht Management-UI       | Rollenbehandlung der Client-Seite       |
| Viewer-API-Anfrage ist erfolgreich | Serverseitige RBAC                    |
| Operator erhält `403`            | Berechtigungsmodell des Endpunkts       |
| Administrator erhält `403`       | Sitzung / CSRF / Endpunkt-Autorisierung |
| Benutzer kann nicht erstellt werden | Admin-Rolle + Validierung           |
| Deaktivierter Benutzer kann sich anmelden | Kontozustand + Sitzungsverwaltung |
| Login vorübergehend blockiert    | Ratenbegrenzung                         |
| Zustandsändernde Anfrage abgelehnt | CSRF / Sitzung                        |
| UI und API stimmen nicht überein | Browserzustand + Server-Autorisierung   |

Das serverseitige Autorisierungsergebnis ist immer wichtiger als die Frage, ob ein Oberflächenelement sichtbar ist.

---

# 69. Nächster Fehlerbehebungsbereich

Die nächsten Diagnosebereiche sind:

```text id="8r5w2q"
Application and audit logging
Container security
Filesystem permissions
Docker runtime configuration
Tests and CI
Diagnostic snapshots
Final recovery checklist
```

Diese Bereiche sollten untersucht werden, ohne die Sicherheitsbasis zu schwächen.

# 70. Anwendungs-Logging

LUMS verwendet Anwendungs-Logging, um Diagnoseinformationen bereitzustellen, ohne sensible Anmeldeinformationen preiszugeben.

Beginnen Sie bei der Untersuchung eines Anwendungsproblems mit den aktuellsten Logs:

```bash id="f6m2qa"
sudo docker logs \
    --tail 200 \
    lums
```

Für kontinuierliche Überwachung:

```bash id="x3v8kp"
sudo docker logs \
    -f \
    lums
```

Reproduzieren Sie das Problem nach Möglichkeit, während Sie die Logs überwachen.

Dies erleichtert die Korrelation von:

```text id="p8k4zw"
User action
    ↓
HTTP request
    ↓
Application event
    ↓
Database operation
    ↓
Agent interaction
```

---

# 71. Anwendungslogs enthalten einen Fehler

Identifizieren Sie zuerst die Komponente, die die Meldung erzeugt hat.

Typische Quellen sind:

```text id="w4c8rn"
Flask application
Gunicorn
Database layer
Authentication
Authorization
Package management
Job execution
Client reporting
```

Gehen Sie nicht davon aus, dass die letzte Log-Meldung die Grundursache ist.

Suchen Sie den ersten relevanten Fehler in der Ereignissequenz.

Korrelieren Sie, wo möglich:

```text id="n6q2vy"
Timestamp
Client
Request
Job ID
Error
Result
```

---

# 72. Audit-Logging

LUMS zeichnet sicherheitsrelevante Anwendungsaktionen im Audit-Log auf.

Audit-Logging ist nützlich bei der Untersuchung von:

```text id="j8r4px"
User changes
Authentication events
Administrative actions
Client management
Token operations
Update-job creation
Security-relevant state changes
```

Ein Audit-Ereignis sollte als Nachweis eines Anwendungsereignisses behandelt werden, nicht als Ersatz für Systemlogs.

Verwenden Sie Anwendungslogs für technische Ausführungsdetails und Audit-Logs für sicherheitsrelevante Anwendungsaktionen.

---

# 73. Audit-Ereignis fehlt

Wenn ein erwartetes Audit-Ereignis fehlt:

1. Identifizieren Sie die genaue Aktion.
2. Identifizieren Sie den API-Endpunkt.
3. Prüfen Sie, ob die Aktion tatsächlich den Server erreicht hat.
4. Inspizieren Sie die Anwendungslogs.
5. Stellen Sie fest, ob die Aktion abgelehnt wurde, bevor das Audit-Ereignis hätte erstellt werden sollen.

Fügen Sie Audit-Datensätze nicht manuell ein, nur damit eine Audit-Spur vollständig erscheint.

Ein Audit-Datensatz sollte einem realen Anwendungsereignis entsprechen.

---

# 74. Audit-Log und Anwendungslog unterscheiden sich

Die beiden Logging-Systeme haben unterschiedliche Zwecke.

Zum Beispiel:

```text id="7q2m5k"
Application log
→ technical execution information

Audit log
→ security-relevant application event
```

Ein Paketmanager-Fehler kann daher im Anwendungs- oder Agent-Log erscheinen, ohne ein separates administratives Audit-Ereignis darzustellen.

Umgekehrt sollte eine Benutzerverwaltungsaktion ein auditierbares Anwendungsereignis erzeugen, selbst wenn die Operation technisch einfach ist.

---

# 75. Sensible Informationen in Logs

Platzieren Sie niemals absichtlich Folgendes in Diagnoseausgaben:

```text id="3m7v9x"
Client tokens
Application secret keys
Passwords
Session secrets
Private keys
TLS private material
```

Wenn ein Diagnosebefehl einen dieser Werte offenlegen würde, verwenden Sie stattdessen eine redigierte oder reine Metadaten-Prüfung.

Überprüfen Sie Logs beim Teilen zur Fehlerbehebung auf Secrets, bevor Sie sie in Tickets, Dokumentation, GitHub-Issues oder Chats kopieren.

---

# 76. Docker-Container-Sicherheit

Der LUMS-Produktionscontainer ist absichtlich gehärtet.

Die erwarteten Sicherheitseigenschaften umfassen:

```text id="z4w6pt"
Non-root application user
Read-only root filesystem
All Linux capabilities dropped
no-new-privileges enabled
No privileged mode
Dedicated writable data volume
Read-only secret mount
Restricted temporary filesystems
```

Wenn eine dieser Eigenschaften unerwartet ändert, behandeln Sie es als Konfigurationsdrift.

Schwächen Sie den Container nicht, um ein Anwendungsproblem zu lösen, es sei denn, die Sicherheitsauswirkungen wurden ausdrücklich bewertet.

---

# 77. Laufzeit-Sicherheit des Containers prüfen

Inspizieren Sie den Container:

```bash id="b8x5jq"
sudo docker inspect lums
```

Für eine fokussierte Laufzeitprüfung:

```bash id="r3n7cw"
sudo docker inspect \
    --format='ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} Privileged={{.HostConfig.Privileged}} CapDrop={{json .HostConfig.CapDrop}} SecurityOpt={{json .HostConfig.SecurityOpt}}' \
    lums
```

Die erwarteten Werte umfassen:

```text id="k5m2zr"
ReadonlyRootfs=true
Privileged=false
CapDrop=[ALL]
SecurityOpt=[no-new-privileges:true]
```

Die genaue Formatierung kann zwischen Docker-Versionen variieren.

Die Sicherheitseigenschaften selbst sind entscheidend.

---

# 78. Container läuft als Root

Die LUMS-Anwendung sollte als ihr dedizierter unprivilegierter Anwendungsbenutzer laufen.

Wenn der Container unerwartet als Root läuft, inspizieren Sie zuerst das Image und die Laufzeitkonfiguration:

```bash id="p6x4nz"
sudo docker inspect \
    --format='{{.Config.User}}' \
    lums
```

Inspizieren Sie dann das Dockerfile.

Lösen Sie Anwendungsberechtigungsprobleme nicht, indem Sie den Produktionscontainer auf Root umstellen.

Wenn ein Verzeichnis Schreibzugriff erfordert, identifizieren Sie den genauen Pfad und stellen Sie fest, ob es persistente Anwendungsdaten oder temporäre Daten sein sollten.

---

# 79. Schreibgeschütztes Root-Dateisystem

Der Produktionscontainer verwendet ein schreibgeschütztes Root-Dateisystem.

Dies schützt das Anwendungsimage vor unnötiger Laufzeitänderung.

Wenn die Anwendung meldet:

```text id="y5k8mc"
Read-only filesystem
Permission denied
Cannot create file
Cannot write temporary data
```

stellen Sie zuerst fest, **wohin** die Anwendung zu schreiben versucht.

Erwartete beschreibbare Speicherorte sind absichtlich begrenzt.

Persistente Anwendungsdaten gehören in:

```text id="q9m3xr"
/var/lib/lums
```

Temporäre Laufzeitdaten können die konfigurierten temporären Dateisysteme verwenden.

Deaktivieren Sie `--read-only` nicht nur deshalb, weil ein Anwendungspfad unerwartet beschreibbar ist.

---

# 80. `/tmp` ist nicht beschreibbar

Wenn die Anwendung temporären Speicher benötigt, prüfen Sie das temporäre Dateisystem:

```bash id="a7w4vn"
sudo docker inspect \
    --format='{{json .HostConfig.Tmpfs}}' \
    lums
```

Der Produktionscontainer stellt ein eingeschränktes `/tmp` bereit.

Das temporäre Dateisystem ist nur für flüchtige Daten vorgesehen.

Persistente Daten dürfen dort nicht gespeichert werden.

---

# 81. Secret-Mount-Probleme

Das LUMS-Anwendungssecret wird über einen geschützten Datei-Mount bereitgestellt.

Das Secret sollte nicht direkt in das Image eingebettet werden.

Wenn LUMS ein fehlendes Secret meldet, inspizieren Sie zuerst die Laufzeitkonfiguration:

```bash id="j4p7zx"
sudo docker inspect \
    lums
```

Prüfen Sie, dass der Secret-Mount existiert und schreibgeschützt ist.

Geben Sie den Inhalt des Secrets nicht aus.

Eine nützliche Diagnose ist, zu prüfen, dass die Datei existiert und die erwarteten Berechtigungen hat, ohne ihren Inhalt anzuzeigen.

---

# 82. Secret-Datei fehlt

Wenn die Secret-Datei auf dem Host nicht existiert, kann der Container nicht korrekt authentifizieren oder initialisieren.

Stellen Sie zuerst fest, ob der erwartete Secret-Pfad existiert.

Erstellen Sie das Secret nicht zufällig neu.

Ein Ersatz-Secret kann bestehende Sitzungen oder andere kryptografische Zustände ungültig machen, je nachdem, wie die Anwendung es verwendet.

Jeder absichtliche Secret-Ersatz muss daher als kontrollierte Sicherheitsoperation behandelt werden.

---

# 83. Persistentes Volume ist nicht beschreibbar

Wenn LUMS keine Anwendungsdaten schreiben kann, inspizieren Sie das Volume:

```bash id="y6c2mt"
sudo docker volume inspect \
    lums-data
```

Inspizieren Sie dann die Container-Mounts:

```bash id="e5w8rq"
sudo docker inspect \
    --format='{{json .Mounts}}' \
    lums
```

Die Anwendungsdatenbank muss auf dem persistenten beschreibbaren Volume liegen.

Machen Sie nicht das gesamte Container-Dateisystem beschreibbar als Workaround.

Die korrekte Lösung besteht darin, den spezifischen Pfad zu identifizieren, der Persistenz erfordert.

---

# 84. Docker-Container startet, aber Anwendung schlägt fehl

Wenn der Container startet und sofort beendet wird:

```bash id="t7x3mp"
sudo docker ps -a \
    --filter name=lums
```

Inspizieren Sie dann:

```bash id="n4q6vz"
sudo docker logs \
    --tail 200 \
    lums
```

Häufige Ursachen sind:

```text id="w3j8kc"
Application startup error
Missing secret
Database initialization error
Migration failure
Invalid environment configuration
Permission problem
Dependency problem
```

Bauen Sie nicht sofort das Image neu.

Stellen Sie fest, ob das Problem im Image, in der Laufzeitkonfiguration, in persistenten Daten oder in der externen Konfiguration liegt.

---

# 85. Docker-Image vs. Container-Konfiguration

Ein funktionierendes Image kann trotzdem wegen falscher Laufzeitkonfiguration fehlschlagen.

Unterscheiden Sie immer:

```text id="s7q2mj"
Docker image
    +
Container runtime configuration
    +
Persistent volume
    +
Secret/configuration
```

Zum Beispiel:

```text id="m5v9rz"
Image is valid
      +
Wrong volume
      =
Application failure
```

oder:

```text id="r6c3pk"
Image is valid
      +
Missing secret
      =
Application startup failure
```

Bauen Sie kein ansonsten gültiges Image neu, um ein Laufzeitkonfigurationsproblem zu beheben.

---

# 86. Docker-Build-Probleme

Wenn ein neues Image nicht gebaut werden kann, inspizieren Sie zuerst das Dockerfile.

Prüfen Sie das Basisimage und die Abhängigkeitsdefinitionen.

Das Produktions-Dockerfile verwendet einen gepinnten Python-Basisimage-Digest.

Dies bietet Reproduzierbarkeit und verhindert, dass der Build stillschweigend auf eine unzusammenhängende Basisimage-Revision wechselt.

Wenn ein Build plötzlich sein Verhalten ändert, vergleichen Sie:

```text id="e3y7pn"
Dockerfile
Base-image digest
Requirements
Application source
Build context
```

---

# 87. `.dockerignore`-Probleme

Der Docker-Build-Kontext sollte keine unnötigen lokalen Dateien oder sensibles Material enthalten.

Das Repository verwendet `.dockerignore`, um Dateien wie Folgt auszuschließen:

```text id="k2x8vw"
Local backups
Temporary files
Editor artifacts
Backup copies
Other unnecessary runtime material
```

Wenn ein Build unerwartet eine Datei enthält, die nicht vorhanden sein sollte, inspizieren Sie:

```bash id="q5m8cz"
cat .dockerignore
```

Lösen Sie Build-Kontext-Probleme nicht, indem Sie sensible Dateien in das Image kopieren.

---

# 88. Dateisystem-Berechtigungsprobleme

Wenn LUMS Berechtigungsfehler meldet, identifizieren Sie zuerst den genauen Pfad.

Nützliche Informationen:

```bash id="p4r7yn"
sudo docker inspect \
    lums
```

und:

```bash id="n8v2km"
sudo docker logs \
    --tail 200 \
    lums
```

Die wichtige Unterscheidung ist:

```text id="x6c9pw"
Application data
Temporary data
Application source
Secret material
Host configuration
```

Jede hat andere erwartete Berechtigungen.

Ändern Sie nicht rekursiv Eigentümer oder Berechtigungen im gesamten Dateisystem als Fehlerbehebungs-Abkürzung.

---

# 89. Produktionskonfigurationsdrift

Konfigurationsdrift tritt auf, wenn die laufende Umgebung nicht mehr zur beabsichtigten Sicherheitsbasis passt.

Beispiele sind:

```text id="r5j8tx"
Container runs as root
Port 5050 exposed externally
Read-only filesystem disabled
Capabilities restored
Privileged mode enabled
Secret mounted read-write
Unexpected container running
```

Wenn Drift erkannt wird:

1. Den aktuellen Zustand aufzeichnen.
2. Feststellen, wann er sich geändert hat.
3. Die verantwortliche Konfiguration identifizieren.
4. Die Konfiguration bewusst korrigieren.
5. Die relevante Sicherheitsverifikation erneut ausführen.

Nehmen Sie nicht mehrere unzusammenhängende Änderungen gleichzeitig vor.

---

# 90. Unerwartete Netzwerkexposition

Der Anwendungsport sollte lokal bleiben:

```text id="n7w4cp"
127.0.0.1:5050
```

Prüfen Sie Listener:

```bash id="y2m6vk"
sudo ss -lntp
```

Wenn `5050` auf einer Nicht-Loopback-Adresse exponiert ist, untersuchen Sie die Docker-Port-Zuordnung sofort.

Setzen Sie den Anwendungsport nicht aus, nur weil Nginx schwierig zu diagnostizieren erscheint.

Die beabsichtigte Architektur ist:

```text id="h3x8qm"
Network
   ↓
Nginx :443
   ↓
127.0.0.1:5050
   ↓
LUMS
```

---

# 91. Unerwartete Docker-Container

Listen Sie alle Container auf:

```bash id="c6w9rz"
sudo docker ps -a
```

Unerwartete Container sollten identifiziert werden, bevor sie entfernt werden.

Prüfen Sie:

```text id="m8x2kf"
Container name
Image
Creation time
Ports
Volumes
Restart policy
```

Löschen Sie keinen unbekannten Container, ohne festzustellen, ob er Teil der LUMS-Bereitstellung oder eine erforderliche Fallback-Umgebung ist.

---

# 92. Docker-Volume darf während normaler Fehlerbehebung nicht gelöscht werden

Die folgende Operation ist destruktiv:

```bash id="q7v3mc"
sudo docker volume rm lums-data
```

Sie darf nicht als allgemeiner Fehlerbehebungsschritt verwendet werden.

Das Löschen des Volumes kann die Anwendungsdatenbank und den zugehörigen persistenten Zustand entfernen.

Wenn eine saubere Installation absichtlich erforderlich ist, behandeln Sie sie als separate Migrations- oder Wiederherstellungsoperation und verifizieren Sie zuerst Backups.

---

# 93. Sicherheitsbasis nach Laufzeitänderungen

Prüfen Sie nach Änderungen der Produktions-Docker-Konfiguration die Sicherheitsbasis erneut.

Prüfen Sie mindestens:

```text id="z5n8xp"
Container runs as intended user
Root filesystem is read-only
Capabilities are dropped
Privileged mode is disabled
no-new-privileges is enabled
Secret mount is read-only
Database volume is writable
Application port is loopback-only
```

Eine Konfiguration, die die Anwendung funktionieren lässt, aber diese Eigenschaften schwächt, sollte nicht als erfolgreiche Behebung betrachtet werden.

---

# 94. Nächster Fehlerbehebungsbereich

Die verbleibenden Fehlerbehebungsthemen sind:

```text id="v4m7yx"
Tests and CI
Diagnostic snapshots
Common failure combinations
Recovery principles
Final troubleshooting checklist
```

Die abschließenden Abschnitte bieten ein kompaktes Verfahren zum Sammeln ausreichender Informationen, um ein Problem zu diagnostizieren, ohne die Produktionsumgebung unnötig zu verändern.

# 95. Tests und CI

Automatisierte Tests sind ein wichtiger Bestandteil der LUMS-Fehlerbehebung.

Bevor Sie ein Produktionsproblem als Anwendungsdefekt untersuchen, prüfen Sie, ob das relevante Verhalten bereits durch die Testsuite abgedeckt ist.

Die aktuelle vollständige Testsuite sollte bestehen, bevor ein Release als bereit gilt.

Führen Sie die vollständige Testsuite aus dem Repository aus:

```bash id="m4x8kp"
./.venv-test/bin/pytest -q
```

Ein erfolgreicher Lauf sollte alle Tests als bestanden melden.

Die Anzahl der Tests ändert sich, während zusätzliche Tests hinzugefügt werden. Die wichtige Bedingung ist, dass die vollständige Testsuite erfolgreich ist, anstatt sich auf eine feste Testanzahl zu verlassen.

---

# 96. Ein Testfehler bedeutet nicht automatisch, dass die Produktion defekt ist

Ein fehlgeschlagener Test kann verursacht werden durch:

```text id="q8r5wy"
Application regression
Test regression
Dependency change
Environment problem
Missing test dependency
Incorrect test configuration
```

Inspizieren Sie zuerst die vollständige Fehlerausgabe.

Ändern Sie die Produktionskonfiguration nicht allein deshalb, weil ein lokaler Test fehlschlägt.

Die korrekte Sequenz ist:

```text id="n4m7tx"
Test failure
    ↓
Read complete error
    ↓
Identify affected component
    ↓
Reproduce locally
    ↓
Determine root cause
    ↓
Apply controlled fix
    ↓
Run relevant tests
    ↓
Run full test suite
```

---

# 97. RBAC-Testfehler

Führen Sie bei der Untersuchung von Autorisierungsproblemen zuerst die RBAC-Tests aus:

```bash id="k6w2pv"
./.venv-test/bin/pytest -q tests/test_rbac.py
```

Die Tests decken rollenspezifisches Verhalten und Autorisierungsgrenzen ab.

Wenn das Problem die Client-Seite betrifft, verwenden Sie nach Bedarf die relevante Teilmenge:

```bash id="z5n8rc"
./.venv-test/bin/pytest -q \
    tests/test_rbac.py -k client_page
```

Schwächen Sie die Autorisierung nicht, damit ein Test besteht.

Ein fehlgeschlagener Autorisierungstest kann auf eine Sicherheitsregression hinweisen.

---

# 98. Paketsuche-Testfehler

Paketverwaltungsfunktionalität hat dedizierte Testabdeckung.

Bei der Untersuchung des Paketsuche-Verhaltens:

```bash id="b7x3mf"
./.venv-test/bin/pytest -q \
    tests/test_package_search.py
```

Wenn der Fehler die Paketausführung oder Job-Ergebnisse betrifft, inspizieren Sie auch die relevanten Job-Ergebnis-Tests.

Die Testsuite sollte verwendet werden, um zu unterscheiden zwischen:

```text id="y9r4nk"
Application logic problem
Package-search problem
Agent problem
Integration problem
```

---

# 99. Tests zur Validierung von Job-Ergebnissen

Die Behandlung von Job-Ergebnissen ist sicherheitssensibel, weil der Server beliebige Client-Eingaben nicht blind vertrauen darf.

Führen Sie bei der Untersuchung der Ergebnisvalidierung die relevanten Tests aus:

```bash id="w6q2vz"
./.venv-test/bin/pytest -q \
    tests/test_job_result.py
```

Ein Fehler hier sollte als Problem der Anwendungskorrektheit und Sicherheit behandelt werden.

Umgehen Sie die Ergebnisvalidierung nicht, damit ein Client-Bericht erfolgreich ist.

---

# 100. CI-Fehler

LUMS verwendet kontinuierliche Integration, um das Projekt zu verifizieren, bevor Änderungen akzeptiert werden.

Wenn CI fehlschlägt:

1. Den fehlgeschlagenen Job identifizieren.
2. Die vollständige Fehlermeldung lesen.
3. Feststellen, ob der Fehler code-, abhängigkeits-, test- oder umgebungsbezogen ist.
4. Lokal reproduzieren, wo möglich.
5. Die Grundursache beheben.
6. Die relevanten Tests ausführen.
7. Die vollständige Testsuite ausführen.

Ignorieren Sie CI-Fehler nicht nur deshalb, weil die Produktionsumgebung derzeit funktional erscheint.

---

# 101. Diagnose-Snapshot

Wenn Sie bei einem LUMS-Problem um Hilfe bitten, sammeln Sie einen minimalen Diagnose-Snapshot.

Das Ziel ist, genügend Informationen bereitzustellen, um die fehlschlagende Komponente zu identifizieren, ohne Secrets offenzulegen.

Ein nützlicher Snapshot umfasst:

```bash id="x8p4qn"
sudo docker ps
```

```bash id="c5m7vz"
sudo docker logs --tail 100 lums
```

```bash id="f2w9yk"
sudo systemctl status nginx --no-pager
```

```bash id="n6r3tx"
sudo systemctl status lums-agent.service --no-pager
```

```bash id="q7v4mc"
sudo systemctl status lums-agent-watcher.service --no-pager
```

```bash id="z3k8wp"
sudo journalctl -u lums-agent.service -n 100 --no-pager
```

```bash id="h5m2rx"
sudo journalctl -u lums-agent-watcher.service -n 100 --no-pager
```

```bash id="p9x6kc"
sudo ss -lntp
```

Verwenden Sie nur die für das Problem relevanten Befehle.

Dumpen Sie nicht die vollständige Umgebung in eine Support-Anfrage.

---

# 102. Diagnose-Snapshot darf keine Secrets enthalten

Prüfen Sie vor dem Teilen von Diagnoseausgaben auf:

```text id="r4m8yn"
Passwords
Client tokens
Application secret keys
Session secrets
Private keys
TLS private material
Credentials
```

Schwärzen Sie sensible Werte vor dem Teilen.

Gehen Sie nicht davon aus, dass ein Log sicher ist, nur weil es von einem Systemdienst stammt.

---

# 103. Fehlerkombinations-Matrix

Einige Symptome lassen sich leichter diagnostizieren, wenn mehrere Komponenten zusammen betrachtet werden.

| Symptom                                       | Wahrscheinlichster zuerst zu prüfender Bereich |
| --------------------------------------------- | ---------------------------------------------- |
| Browser kann keine Verbindung herstellen      | Nginx / TLS / Netzwerk                         |
| Nginx funktioniert, aber Anwendung schlägt fehl | Docker / LUMS                               |
| LUMS funktioniert, aber Client kann nicht berichten | Agent / TLS / Token                      |
| Client berichtet, aber Job bleibt ausstehend  | Watcher / Berechtigung                         |
| Job läuft, aber Paket schlägt fehl            | APT / pacman                                   |
| Paket erfolgreich, aber Ergebnis fehlt        | Agent-Berichterstattung                        |
| Ergebnis erreicht Server, aber UI ist veraltet | API / Datenbank / Browserzustand              |
| Viewer kann Daten verändern                   | Serverseitige RBAC                             |
| Benutzer kann sich nicht anmelden             | Konto / Passwort / Ratenbegrenzung             |
| Login funktioniert, aber Aktion abgelehnt     | RBAC / CSRF                                    |
| Datenbankschreibvorgänge schlagen fehl        | SQLite / Festplatte / Berechtigungen           |
| Container verliert Daten nach Neuerstellung   | Persistente Volume-Konfiguration               |
| Anwendung schreibt auf Root-Dateisystem       | Container-Dateisystem-Konfiguration            |
| Port 5050 ist extern erreichbar               | Docker-/Firewall-Konfiguration                 |

Diese Tabelle identifiziert den ersten Ort zur Untersuchung, nicht notwendigerweise die endgültige Grundursache.

---

# 104. Häufige Fehlerbehebungsfehler

Vermeiden Sie die folgenden Abkürzungen:

## Löschen Sie nicht die Datenbank

```text id="h7k2px"
Deleting lums.db
Deleting lums-data
```

kann persistente Anwendungsdaten zerstören.

---

## Deaktivieren Sie keine Sicherheitskontrollen

Deaktivieren Sie nicht dauerhaft:

```text id="j5r9cw"
RBAC
CSRF protection
TLS validation
Container hardening
Read-only filesystem
no-new-privileges
Capability restrictions
```

Ein Workaround, der eine Sicherheitskontrolle entfernt, ist keine abgeschlossene Behebung.

---

## Führen Sie den Container nicht als privilegiert aus

Vermeiden Sie:

```text id="b3x7mz"
--privileged
```

als Fehlerbehebungslösung.

Wenn die Anwendung zusätzlichen Zugriff erfordert, stellen Sie genau fest, welcher Zugriff erforderlich ist.

---

## Setzen Sie Port 5050 nicht aus

Ändern Sie nicht:

```text id="v8n4qr"
127.0.0.1:5050
```

zu:

```text id="p2m6wy"
0.0.0.0:5050
```

nur um Nginx zu umgehen.

Die Anwendung ist absichtlich hinter dem Reverse-Proxy geschützt.

---

## Ändern Sie Job-Zustände nicht manuell

Vermeiden Sie direkte Änderungen an:

```text id="r7c5xn"
update_jobs
update_job_packages
```

um ein operatives Problem zu verbergen.

Verwenden Sie die Anwendungs-, Agent-, Watcher- und Wiederherstellungsmechanismen.

---

## Löschen Sie Paketmanager-Sperren nicht blind

Eine Sperre kann einen aktiven Paketmanager-Prozess anzeigen.

Identifizieren Sie zuerst den Prozess.

---

## Rotieren Sie Anmeldeinformationen nicht wiederholt

Wiederholte Token- oder Secret-Rotation kann zusätzliche Authentifizierungsprobleme schaffen.

Stellen Sie zuerst fest, welches Credential derzeit konfiguriert ist und welches Credential der Server erwartet.

---

# 105. Wiederherstellungsprinzipien

Die folgenden Prinzipien gelten für alle LUMS-Fehlerbehebungen:

### Zuerst bewahren

Bewahren Sie:

```text id="q3m8vx"
Logs
Job state
Database
Container state
Configuration
Error messages
```

bis das Problem verstanden ist.

### Ändern Sie eine Sache nach der anderen

Wenn mehrere Änderungen gleichzeitig vorgenommen werden, wird die ursprüngliche Ursache schwerer zu identifizieren.

### Verifizieren Sie nach jeder Änderung

Nach einer kontrollierten Änderung:

```text id="z6w2kp"
Re-test
Check logs
Verify state
Confirm security properties
```

### Bevorzugen Sie umkehrbare Änderungen

Verwenden Sie nach Möglichkeit Änderungen, die ohne Zerstörung des Anwendungszustands rückgängig gemacht werden können.

### Halten Sie Sicherheitskontrollen aktiv

Ein erfolgreiches Fehlerbehebungsergebnis darf keine unnötige Sicherheitsregression einführen.

---

# 106. Produktions-Fehlerbehebungssequenz

Für ein allgemeines LUMS-Produktionsproblem verwenden Sie diese Reihenfolge:

```text id="f4n8rx"
1. Identify the symptom
        ↓
2. Identify the affected component
        ↓
3. Inspect current state
        ↓
4. Inspect relevant logs
        ↓
5. Reproduce safely
        ↓
6. Determine the first failing layer
        ↓
7. Apply the smallest required change
        ↓
8. Re-test
        ↓
9. Verify security controls
        ↓
10. Document the result
```

Diese Reihenfolge verhindert, dass unzusammenhängende Komponenten unnötig geändert werden.

---

# 107. Vollständiger Systemdiagnosepfad

Wenn die betroffene Komponente unbekannt ist, folgen Sie dem vollständigen Pfad:

```text id="u7x3mp"
Browser
  │
  ▼
Nginx / HTTPS
  │
  ▼
Docker
  │
  ▼
LUMS API
  │
  ▼
SQLite
  │
  ▼
Update Job
  │
  ▼
Watcher
  │
  ▼
Agent
  │
  ▼
APT / pacman
  │
  ▼
Client state
  │
  ▼
Agent result
  │
  ▼
LUMS API
  │
  ▼
SQLite
  │
  ▼
Web UI
```

Fragen Sie auf jeder Stufe:

```text id="k5r2qy"
Did the request reach this component?

Did this component process it?

Did it produce the expected result?

Did the next component receive that result?
```

Das erste `NEIN` identifiziert normalerweise den Bereich, der untersucht werden muss.

---

# 108. Release-Fehlerbehebung

Bevor Sie ein Release vorbereiten, prüfen Sie:

```text id="m8x4vp"
Full test suite passes
CI passes
Security audit is complete
Documentation is current
Production configuration matches the documented baseline
No unexpected debug configuration remains
No secrets are included in the repository
Docker hardening remains active
RBAC behavior is correct
Package management works
Update-job execution works
Recovery behavior is verified
```

Ein Release sollte nicht allein deshalb erstellt werden, weil die Anwendung erfolgreich startet.

---

# 109. Fehlerbehebungs-Checkliste

Verwenden Sie diese Checkliste, bevor Sie ein Produktionsproblem als gelöst erklären:

```text id="y6q3kn"
[ ] Root cause identified
[ ] Relevant logs inspected
[ ] No unnecessary data was deleted
[ ] No credentials were exposed
[ ] No security control was disabled
[ ] Relevant functionality tested
[ ] Full test suite considered where appropriate
[ ] Docker security baseline verified
[ ] Network exposure verified
[ ] Agent state verified
[ ] Watcher state verified
[ ] Job state verified
[ ] Recovery state verified
[ ] Database state verified where relevant
[ ] Documentation updated if behavior changed
```

---

# 110. Wann die Fehlerbehebung stoppen

Hören Sie auf, Änderungen vorzunehmen, wenn:

```text id="v9m4xr"
The root cause is identified
    AND
The corrective action is understood
    AND
The system is stable
    AND
Security controls remain intact
```

Wenn die Grundursache nicht verstanden ist, bewahren Sie den aktuellen Zustand, anstatt die Umgebung wiederholt zu ändern.

Ein sauber bewahrter Fehler ist leichter zu diagnostizieren als ein teilweise verändertes System.

---

# 111. Abschließendes Wiederherstellungsprinzip

Die wichtigste LUMS-Fehlerbehebungsregel ist:

> **Zuerst beobachten. Zweitens ändern. Drittens verifizieren.**

LUMS enthält mehrere unabhängige Sicherheits- und Ausführungsschichten.

Ein Problem in einer Schicht sollte nicht automatisch zu Änderungen in einer anderen führen.

Der bevorzugte Fehlerbehebungsansatz ist daher:

```text id="c8w5zn"
Observe
   ↓
Classify
   ↓
Isolate
   ↓
Correct
   ↓
Verify
   ↓
Document
```

Dies hält die Fehlerbehebung kontrolliert, reproduzierbar und kompatibel mit der LUMS-Sicherheitsbasis.

---

# 112. Dokumentationspflege

Dieses Dokument sollte aktualisiert werden, wenn sich ein dokumentiertes operatives Verhalten ändert.

Dokumentationsänderungen sollten konsistent bleiben mit:

```text id="q7m3vx"
Security documentation
Deployment documentation
Agent behavior
Watcher behavior
RBAC model
Package-management behavior
Docker runtime configuration
Test baseline
```

Veraltete Fehlerbehebungsanweisungen können gefährlich sein, wenn sie veraltete Befehle oder sicherheitsschwächende Workarounds empfehlen.

Wenn sich ein Produktionsverhalten ändert, aktualisieren Sie die relevante Dokumentation, bevor Sie das Fehlerbehebungsverfahren als abgeschlossen betrachten.

---

# 113. Aktuelle Basis

Die aktuelle von diesem Fehlerbehebungshandbuch dokumentierte LUMS-Basis umfasst:

```text id="m4x8qp"
Agent version: 1.7.0
Watcher version: 1.2.1

Application port:
127.0.0.1:5050

Database:
SQLite

SQLite journal mode:
delete

SQLite busy timeout:
5000 ms

SQLite synchronous:
2

SQLite foreign keys:
Enabled by the application

Container:
Non-root
Read-only root filesystem
Capabilities dropped
no-new-privileges enabled
Privileged mode disabled

RBAC:
Administrator
Operator
Viewer

Viewer:
Clients + Installed Software only

Full test suite:
Passing baseline
```

Die genaue Testanzahl kann sich ändern, während das Projekt wächst.

Die Sicherheits- und Architektureigenschaften sind die wichtige Basis.

---

# 114. Ende des Fehlerbehebungshandbuchs

Die LUMS-Fehlerbehebung sollte evidenzbasiert und sicherheitsbewusst bleiben.

Im Zweifelsfall:

```text id="r9x4kw"
Preserve the state.
Inspect the evidence.
Identify the failing layer.
Make the smallest safe change.
Verify the result.
Document what happened.
```

Tauschen Sie Sicherheit oder Datenintegrität nicht gegen einen schnellen Workaround ein.

---

**Ende des LUMS-Fehlerbehebungshandbuchs**
