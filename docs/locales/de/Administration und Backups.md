# LUMS — Administrationshandbuch

> **Linux Update Management ohne das Rauschen.**

Dieses Handbuch beschreibt die tägliche Administration und den Betrieb von LUMS, nachdem Server und Clients installiert wurden.

Es konzentriert sich auf administrative Aufgaben, die über die LUMS-Weboberfläche ausgeführt werden, sowie auf kontrollierte operative Aufgaben auf dem LUMS-Server und verwalteten Clients.

Installationsverfahren sind separat in `install.md` dokumentiert.

Fehlerbehebungsverfahren sind separat in `troubleshooting.md` dokumentiert.

Sicherheitsarchitektur und Audit-Informationen sind separat in `security.md` dokumentiert.

---

## Erste Schritte: Tägliche Administration

Dieses Handbuch richtet sich an die Person, die für eine bestehende LUMS-Installation verantwortlich ist. Die detaillierten technischen Abschnitte werden auf Englisch geführt. Beginnen Sie mit diesen Begriffen:

* **Benutzerkonto:** bestimmt, was eine Person in der LUMS-Weboberfläche tun darf. Teilen Sie keine Konten; geben Sie jeder Person ihr eigenes Konto.
* **Client:** ein verwalteter Linux-Computer. Sein Client-Token ist ein Secret und nicht dasselbe wie ein Web-Konto-Passwort.
* **Update-Job:** eine angeforderte Operation, die der Agent abruft und mit APT oder pacman auf dem Zielcomputer ausführt. Prüfen Sie Ziel und Pakete, bevor Sie ihn starten.
* **Backup:** eine separate, verifizierte Kopie der Datenbank. Eine Kopie im selben Docker-Volume schützt nicht vor dem Verlust dieses Volumes.
* **Upgrade:** ersetzt die Container-Version, nicht die Datenbank. Ein normales Upgrade darf `lums-data` nicht löschen oder neu erstellen.

### Sichere Checkliste vor einer Änderung

1. Prüfen Sie, ob Update-Jobs laufen und ob ein Wartungsfenster erforderlich ist.
2. Bestätigen Sie, dass ein aktuelles, nutzbares Datenbank-Backup existiert.
3. Dokumentieren Sie das laufende Image, die Container-Einstellungen und die Datenpfade.
4. Bauen und testen Sie das neue Image, bevor Sie den aktiven Container stoppen.
5. Ersetzen Sie den Container mit denselben Daten-, Secret- und Backup-Mounts und denselben Sicherheitsoptionen.
6. Prüfen Sie nach dem Start Containerstatus, Logs, HTTPS-Anmeldung und Daten.
7. Behalten Sie den alten Container als Rollback-Option, bis die neue Version verifiziert wurde.

**Führen Sie nicht aus:** `docker volume rm lums-data`, `docker system prune --volumes` oder andere Löschbefehle als Teil eines normalen Upgrades. Sie können Daten dauerhaft entfernen. Wenn Sie unsicher sind, welcher Container oder Pfad aktiv ist, halten Sie an und inspizieren Sie zuerst die aktuelle Einrichtung; kopieren Sie keinen Beispielbefehl, ohne ihn zu prüfen.

---

## 1. Administrationsübersicht

LUMS bietet zentrale Administration von Linux-Softwareinventar, verfügbaren Updates, Paketoperationen, Update-Jobs, verwalteten Clients, Benutzern und operativer Historie.

Die administrative Oberfläche bietet drei Rollenvorlagen:

* **Administrator**
* **Operator**
* **Viewer**

Wenn ein Konto erstellt wird, füllt die ausgewählte Rolle eine empfohlene Menge von Berechtigungen aus. Administratoren können diese Berechtigungen pro Benutzer anpassen; die gespeicherten Berechtigungen, nicht die Rollenbezeichnung, bestimmen den Zugriff.

LUMS trennt außerdem serverseitige administrative Operationen von clientseitiger Paketausführung.

Der normale operative Ablauf ist:

```text
Administrator / Operator
        │
        ▼
   LUMS Web UI
        │
        ▼
     LUMS API
        │
        ▼
      SQLite
        │
        ▼
   Managed Client
        │
        ▼
 APT / pacman / system
        │
        ▼
      Result
        │
        ▼
     LUMS API
        │
        ▼
      SQLite
        │
        ▼
    Web Interface
```

Der LUMS-Server führt keine paketverwaltungsbezogenen Befehle direkt auf verwalteten Clients aus.

Paketoperationen werden vom LUMS Agent ausgeführt, der auf dem verwalteten System installiert ist.

---

## 2. Administrative Verantwortlichkeiten

Die LUMS-Administration kann in mehrere Bereiche unterteilt werden.

### Benutzeradministration

Administratoren verwalten:

* LUMS-Benutzer
* Benutzerrollen
* Kontostatus
* administrativen Zugriff

Die Benutzerverwaltung erfordert die Berechtigung `users.manage`.

Die Administrator-Vorlage enthält diese Berechtigung standardmäßig.

Operatoren und Viewer erhalten sie standardmäßig nicht.

---

### Client-Administration

Administratoren verwalten:

* registrierte Clients
* Client-Status
* Client-Authentifizierung
* Client-Tokens
* Token-Rotation
* Aktivierung und Deaktivierung von Clients

Die Client-Administration erfordert die Berechtigung `clients.manage`, da die Client-Authentifizierung bestimmt, welche Systeme an LUMS berichten dürfen.

---

### Update-Administration

Die Vorlagen Administrator und Operator gewähren Berechtigungen zum:

* Anzeigen verfügbarer Updates
* Erstellen von Update-Jobs
* Ausführen von Paketoperationen
* Überprüfen des Update-Verlaufs
* Verwalten einzelner Pakete
* Durchführen von Systemupdates

Die Viewer-Vorlage ist schreibgeschützt und kann keine Update-Operationen durchführen.

---

### Paketadministration

LUMS unterstützt paketverwaltungsbezogene Operationen über den nativen Paketmanager des Clients.

Aktuell unterstützte Paketverwaltungs-Backends umfassen:

* **APT/dpkg** für Debian-basierte Systeme
* **pacman** für Arch Linux

LUMS ersetzt nicht den Paketmanager des Betriebssystems.

Stattdessen bietet LUMS eine zentrale Oberfläche zum Anfordern und Verfolgen von Paketoperationen.

---

### Operative Administration

Administratoren und Operatoren müssen möglicherweise überwachen:

* laufende Update-Jobs
* fehlgeschlagene Jobs
* abgeschlossene Jobs
* Client-Berichterstattung
* Reboot-Anforderungen
* Paketmanager-Fehler
* Audit-Aktivität

Die detaillierten Fehlerbehebungsverfahren für diese Zustände sind in `troubleshooting.md` dokumentiert.

---

## 3. Administrative Rollen

LUMS bietet derzeit drei Rollen.

| Rolle         | Zweck                                             |
| ------------- | ------------------------------------------------- |
| Administrator | Vollständige administrative Kontrolle             |
| Operator      | Tägliches operatives Management                    |
| Viewer        | Schreibgeschützte Client- und Software-Sichtbarkeit |

Jede Rolle ist eine Berechtigungsvorlage. Die individuell gespeicherten Berechtigungen des Kontos werden serverseitig durchgesetzt.

Das Ausblenden eines Oberflächenelements gilt daher nicht allein als Sicherheitskontrolle.

Nicht autorisierte API-Operationen müssen ebenfalls vom Server abgelehnt werden.

---

## 4. Administrator

Die Administrator-Vorlage bietet standardmäßig den vollständigen Satz von LUMS-Anwendungsberechtigungen.

Administratoren können:

* verwaltete Clients anzeigen
* installierte Software anzeigen
* verfügbare Updates anzeigen
* Update-Jobs erstellen und ausführen
* Update-Verlauf überprüfen
* paketverwaltungsbezogene Operationen durchführen
* Systemwartung durchführen
* Clients erstellen
* Clients deaktivieren
* Client-Tokens rotieren
* LUMS-Benutzer erstellen und verwalten
* Rollenvorlagen und individuelle Berechtigungen zuweisen

Vollständige Berechtigungen der Administrator-Vorlage sollten nur Benutzern gewährt werden, die sie benötigen.

Administratorkonten sollten nicht für routinemäßige schreibgeschützte Überwachung verwendet werden, wenn ein Operator- oder Viewer-Konto ausreicht.

---

## 5. Operator

Die Operator-Vorlage ist für die tägliche Update- und Systemadministration vorgesehen.

Operatoren können:

* verwaltete Clients anzeigen
* installierte Software anzeigen
* verfügbare Updates anzeigen
* Update-Jobs erstellen und ausführen
* Update-Verlauf überprüfen
* paketverwaltungsbezogene Operationen durchführen
* Systemwartung durchführen

Die Operator-Vorlage gewährt nicht:

* LUMS-Benutzer erstellen oder verwalten
* Benutzerrollen zuweisen
* Clients erstellen oder deaktivieren
* Client-Tokens rotieren

Diese Standardtrennung ermöglicht routinemäßige Update-Operationen, ohne Konto- und Client-Management-Privilegien zu gewähren. Einzelne Gewährungen können von einem Benutzer mit `users.manage` geändert werden.

---

## 6. Viewer

Die Viewer-Vorlage bietet schreibgeschützte Sichtbarkeit.

Viewer können:

* verwaltete Clients anzeigen
* installierte Software anzeigen

Die Viewer-Vorlage gewährt nicht die folgenden administrativen Funktionen:

* Verwaltung verfügbarer Updates
* Erstellung von Update-Jobs
* Ausführung von Update-Jobs
* Update-Verlauf
* Paketverwaltung
* Systemwartung
* Benutzerverwaltung
* Client-Verwaltung
* Token-Rotation

Die entsprechenden mutierenden API-Operationen sind ebenfalls serverseitig geschützt.

Viewer-Zugriff ist daher für Benutzer vorgesehen, die Sichtbarkeit ohne operative Kontrolle benötigen.

---

## 7. Richtlinien zur Rollenauswahl

Verwenden Sie die kleinste Rolle, die die erforderliche Funktionalität bietet.

### Administrator

Verwenden Sie diese Rolle, wenn der Benutzer verwalten muss:

* Benutzer
* Rollen
* Clients
* Client-Authentifizierung
* Tokens
* Updates
* Pakete
* Systemoperationen

### Operator

Verwenden Sie diese Rolle, wenn der Benutzer routinemäßige operative Arbeit durchführen muss wie:

* Updates prüfen
* Pakete installieren
* Pakete entfernen
* Pakete aktualisieren
* Update-Jobs ausführen
* Job-Verlauf überprüfen

### Viewer

Verwenden Sie diese Rolle, wenn der Benutzer nur Sichtbarkeit benötigt in:

* Clients
* installierte Software

---

## 8. Administratives Sicherheitsprinzip

Die LUMS-Administration folgt dem Prinzip der geringsten Privilegien.

Administrativer Zugriff sollte auf die für die Aufgabe des Benutzers erforderliche Funktionalität beschränkt werden.

Insbesondere:

* Verwenden Sie keine Administratorkonten für routinemäßige Anzeige
* Teilen Sie keine Konten zwischen Administratoren
* Teilen Sie keine Client-Tokens
* Legen Sie keine Anmeldeinformationen in der Dokumentation ab
* Geben Sie Client-Tokens nicht in Screenshots oder Logs preis
* Umgehen Sie die LUMS-Weboberfläche nicht durch direkte Datenbankänderung, es sei denn, ein dokumentiertes Wiederherstellungsverfahren verlangt dies ausdrücklich

Wenn eine administrative Operation fehlschlägt, untersuchen Sie die Ursache, bevor Sie persistenten Zustand ändern.

Verwenden Sie das Prinzip:

> **Zuerst beobachten. Zweitens ändern. Drittens verifizieren.**

---

## 9. Administrativer Arbeitsablauf

Ein normaler administrativer Arbeitsablauf sollte dieser Sequenz folgen:

```text
1. Authenticate
      │
      ▼
2. Verify role
      │
      ▼
3. Select client / operation
      │
      ▼
4. Review current state
      │
      ▼
5. Perform required operation
      │
      ▼
6. Monitor job
      │
      ▼
7. Verify result
      │
      ▼
8. Review history / audit information
```

Administrative Aktionen sollten nach der Ausführung immer verifiziert werden.

Eine erfolgreiche API-Anfrage beweist für sich genommen nicht, dass die angeforderte Paket- oder Systemoperation erfolgreich abgeschlossen wurde.

Der vom verwalteten Client gemeldete Endzustand ist das relevante operative Ergebnis.

---

## 10. Trennung der Dokumentation

Das LUMS-Dokumentationsset ist absichtlich in separate operative Handbücher unterteilt.

| Dokument             | Zweck                                        |
| -------------------- | -------------------------------------------- |
| `install.md`         | Installation und Erstbereitstellung          |
| `administration.md`  | Tägliche Administration                       |
| `security.md`        | Sicherheitsarchitektur und Audit-Ergebnisse  |
| `troubleshooting.md` | Diagnose und Wiederherstellung                |

Dieses Handbuch sollte daher die detaillierten Installations- und Fehlerbehebungsverfahren nicht duplizieren.

Stattdessen beschreibt es, was Administratoren verwalten können, was jede Operation bedeutet und wie normale administrative Arbeitsabläufe durchgeführt werden.

## 11. Benutzerverwaltung

Die Benutzerverwaltung ist für Benutzer mit der Berechtigung `users.manage` verfügbar.

Administratoren können LUMS-Anwendungskonten über die dedizierte Benutzerverwaltungsoberfläche erstellen und verwalten.

Benutzerkonten sind von der Authentifizierung verwalteter Clients getrennt.

Ein LUMS-Benutzer authentifiziert sich mit einem Anwendungskonto an der Webanwendung.

Ein verwalteter Client authentifiziert sich mit einem Client-Token an der LUMS-API.

Diese Authentifizierungsmechanismen dürfen nicht verwechselt werden.

```text
LUMS User
    │
    │ username + password
    ▼
Web Interface
    │
    ▼
LUMS Application

Managed Client
    │
    │ client token
    ▼
LUMS API
```

---

## 12. Benutzer erstellen

Benutzer mit `users.manage` können neue LUMS-Benutzer erstellen.

Beim Erstellen eines Benutzers gibt der Administrator an:

* Benutzername
* Passwort
* eine Rollenbezeichnung, wobei eine Rollenvorlage für die spätere Berechtigungszuweisung verfügbar ist

Verfügbare Rollenvorlagen sind:

* `administrator`
* `operator`
* `viewer`

Der Server validiert die übergebenen Werte, bevor er das Konto erstellt.

Neue Konten starten ohne Berechtigungen. Nach der Erstellung können Administratoren einzelne Kontrollkästchen zuweisen oder eine der Rollenvorlagen anwenden. Das Anwenden einer Vorlage wählt deren Standardberechtigungen vor, die dann angepasst werden können. Verfügbare Berechtigungen sind:

| Berechtigung      | Gewährter Zugriff                                    |
| ----------------- | ---------------------------------------------------- |
| `clients.view`    | Client-Liste und Systeminformationen anzeigen       |
| `software.view`   | Installierte Software anzeigen                      |
| `updates.view`    | Updates, Jobs und Update-Verlauf anzeigen           |
| `packages.search` | Paket-Repositories durchsuchen                      |
| `jobs.manage`     | Paketoperationen und Update-Jobs erstellen          |
| `clients.manage`  | Clients registrieren/entfernen und Client-Tokens rotieren |
| `users.manage`    | Benutzer erstellen und Rollen, Berechtigungen und interne Notizen verwalten |
| `backups.manage`  | Datenbank-Backups erstellen und inspizieren         |

Client-bezogene Berechtigungen erfordern `clients.view`; `jobs.manage` erfordert außerdem `updates.view`. LUMS verhindert das Entfernen des letzten aktiven Kontos mit `users.manage`, sodass Administratoren sich nicht versehentlich aussperren können.

Passwörter werden nicht im Klartext gespeichert.

LUMS verwendet Argon2-basiertes Passwort-Hashing für Anwendungsanmeldeinformationen.

Prüfen Sie nach der Erstellung, dass:

* der Benutzername in der Benutzerliste erscheint
* die Rollenvorlage und die individuellen Berechtigungen korrekt sind
* das Konto aktiviert ist
* der Benutzer sich erfolgreich authentifizieren kann

Übertragen Sie Passwörter nicht über Dokumentation, Tickets, Screenshots oder andere unsichere Kanäle.

---

## Datenbank-Backup-Oberfläche

Benutzer mit der Berechtigung `backups.manage` können SQLite-Backups über **Datenbank-Backups** erstellen. Administratorkonten erhalten diese Berechtigung über die Migration `005-backup-permission`; neue Konten erhalten sie durch Anwenden der Administrator-Vorlage oder können sie explizit erhalten.

Die Oberfläche unterstützt native `.db`- und komprimierte `.db.gz`-Dateien. Sie verwendet die Online-Backup-API von SQLite, validiert die fertiggestellte Datenbank und speichert Dateien mit Nur-Eigentümer-Berechtigungen. Die UI listet die zehn neuesten Dateien auf. Backups werden von LUMS nicht verschlüsselt, automatisch gelöscht, geplant, heruntergeladen oder wiederhergestellt; Administratoren mit `backups.manage` können einzelne Backups nach Bestätigung aus der Liste löschen. Schützen Sie das Ziel entsprechend.

Das Basis-Zielverzeichnis wird durch die serverseitige Einstellung `LUMS_BACKUP_DIR` festgelegt. Die Oberfläche erlaubt die Auswahl eines relativen Unterverzeichnisses unterhalb dieser Basis und erstellt es bei Bedarf; absolute Pfade, Parent-Traversal und symbolisch verlinkte Unterverzeichnisse werden abgelehnt. Host-Pfade müssen vom Serveradministrator in Docker gemountet werden. Für eine Docker-Bereitstellung erstellen Sie ein separates Host-Verzeichnis, das für die UID/GID `10001` des Containers beschreibbar ist:

```bash
sudo install -d -o 10001 -g 10001 -m 0700 /var/backups/lums
```

Fügen Sie diese Optionen zur LUMS-Container-Konfiguration hinzu:

```bash
-v /var/backups/lums:/var/backups/lums \
-e LUMS_BACKUP_DIR=/var/backups/lums \
```

Verwenden Sie eine separate Festplatte oder Remote-Speicher für Resilienz gegen Host-Ausfall. Zum Beispiel: Mounten Sie zuerst ein NAS auf dem Debian-Host und verwenden Sie dann diesen gemounteten Pfad als linke Seite des Docker-Bind-Mounts. Die Backup-UI zeigt das container-seitige Basisverzeichnis an; der ausgewählte relative Pfad liegt darunter. Das Backup-Ziel muss innerhalb des Containers verfügbar und beschreibbar sein; andernfalls meldet die Oberfläche, dass der Backup-Speicher nicht verfügbar ist.

Für Wiederherstellungsschritte siehe [`server/static/backup-restore.md`](server/static/backup-restore.md).

---

## 13. Benutzerrollen

Wählen Sie eine Rollenvorlage entsprechend dem minimal erforderlichen Privileg und überprüfen Sie dann die individuellen Berechtigungen für jedes Konto.

| Rollenvorlage | Benutzerverwaltung | Client-Verwaltung | Updates | Paketverwaltung | Schreibgeschützter Zugriff |
| ------------- | -----------------: | ----------------: | ------: | --------------: | -------------------------: |
| Administrator |                Ja  |               Ja  |     Ja  |             Ja  |                        Ja  |
| Operator      |                Nein |              Nein |     Ja  |             Ja  |                        Ja  |
| Viewer        |                Nein |              Nein |    Nein |            Nein |                        Ja  |

Dies sind Standardwerte, keine festen Grenzen. Administratoren können die Berechtigungen jedes Benutzers anpassen. Die Rollendurchsetzung erfolgt auf dem Server über die resultierenden benutzerspezifischen Berechtigungen.

Die Weboberfläche spiegelt die zugewiesene Rolle wider, aber der Server bleibt die maßgebliche Sicherheitsgrenze.

---

## 14. Benutzerkonten deaktivieren

Wenn ein Konto keinen Zugriff mehr auf LUMS haben soll, deaktivieren Sie das Konto, anstatt die Anmeldeinformationen zu teilen oder umzuwidmen.

Beispiele sind:

* ein Administrator verlässt das Projekt
* ein Operator benötigt keinen Zugriff mehr
* vorübergehende Entfernung administrativen Zugriffs
* Sicherheitsreaktion auf ein kompromittiertes Konto

Prüfen Sie nach dem Deaktivieren eines Kontos, dass die Authentifizierung abgelehnt wird.

Bestehende authentifizierte Sitzungen sollten bei kontosicherheitsbezogenen Untersuchungen ebenfalls berücksichtigt werden.

Ändern Sie die `users`-Tabelle nicht manuell, es sei denn, ein dokumentiertes Wiederherstellungsverfahren verlangt ausdrücklich einen Eingriff auf Datenbankebene.

---

## 15. Passwort-Administration

Passwörter sind Anwendungsanmeldeinformationen und müssen als sensible Informationen behandelt werden.

Administratoren sollten sicherstellen, dass:

* Passwörter nicht geteilt werden
* Passwörter nicht in Git gespeichert werden
* Passwörter nicht in der Dokumentation abgelegt werden
* Passwörter nicht in Screenshots aufgenommen werden
* Passwörter nicht unnötig in die Shell-Historie geschrieben werden
* Benutzer ihre Anmeldeinformationen über einen geeigneten sicheren Kanal erhalten

LUMS speichert Passwort-Hashes statt Klartextpasswörter.

Wenn ein Passwort vermutlich kompromittiert ist, ersetzen Sie es über das entsprechende Kontoverwaltungsverfahren, anstatt zu versuchen, das ursprüngliche Passwort wiederherzustellen.

---

## 16. Sitzungen

LUMS verwendet authentifizierte Anwendungssitzungen für den Webzugriff.

Die Sitzungsverwaltung ist Teil der Sicherheitsgrenze der Anwendung.

Administratoren sollten eine unerwartete authentifizierte Sitzung als Sicherheitsereignis behandeln, wenn das zugehörige Konto keinen Zugriff mehr haben sollte.

Relevante Situationen sind:

* deaktiviertes Konto erscheint weiterhin aktiv
* unerwarteter administrativer Zugriff
* vermutete Kompromittierung von Anmeldeinformationen
* unerwartete Browsersitzung
* Sicherheitsuntersuchung

Für detaillierte Sitzungs- und Authentifizierungsfehlerbehebung siehe `troubleshooting.md`.

---

## 17. Login-Ratenbegrenzung

LUMS wendet Ratenbegrenzung auf wiederholte fehlgeschlagene Login-Versuche an.

Die aktuelle Progression ist:

| Fehlgeschlagene Versuche | Sperrzeit   |
| -----------------------: | ----------: |
|                        5 |  30 Sekunden |
|                        6 |  60 Sekunden |
|                        7 | 120 Sekunden |
|                       8+ | 300 Sekunden |

Der Rate-Limit-Zustand wird in SQLite persistiert.

Ein erfolgreicher Login löscht den zutreffenden Fehlversuchs-Zustand.

Wiederholte Authentifizierungsfehler sollten untersucht werden, anstatt den Rate-Limiter zu umgehen.

Mögliche Ursachen sind:

* falsche Anmeldeinformationen
* veraltete gespeicherte Anmeldeinformationen
* ein automatisierter Client mit falschen Anmeldeinformationen
* wiederholte manuelle Login-Versuche
* ein möglicher Credential-Angriff

---

## 18. Client-Verwaltung

Verwaltete Clients sind Linux-Systeme, auf denen der LUMS Agent läuft.

Ein Client liefert LUMS Informationen wie:

* Client-Identität
* installierte Software
* verfügbare Updates
* Paketverwaltungsergebnisse
* Update-Job-Ergebnisse
* Reboot-Zustand
* operativer Status

Der LUMS-Server speichert den Client-Zustand und stellt ihn über die Weboberfläche bereit.

Der Client führt die tatsächlichen Paketverwaltungsoperationen lokal aus.

---

## 19. Client-Authentifizierung

Jeder verwaltete Client authentifiziert sich bei LUMS mit einem Client-Token.

Der Token fungiert als Anmeldeinformation für den verwalteten Client.

Behandeln Sie Client-Tokens mit derselben Sorgfalt wie Passwörter.

Niemals:

* Tokens in Git committen
* Tokens in öffentliche Dokumentation aufnehmen
* Tokens in Screenshots aufnehmen
* Tokens in Issue-Tracker einfügen
* Tokens in diagnostischer Ausgabe preisgeben
* den Token eines Clients mit einem anderen Client teilen

Ein Token sollte nur auf dem Client installiert werden, für den er ausgestellt wurde.

---

## 20. Client-Registrierung

Ein neuer Client muss zuerst bei LUMS registriert werden.

Der Registrierungsprozess etabliert die serverseitige Client-Identität und das Authentifizierungs-Credential.

Nach der Registrierung:

1. den LUMS Agent installieren
2. den Client-Token konfigurieren
3. den LUMS-Serverendpunkt konfigurieren
4. TLS-Vertrauen herstellen
5. einen initialen Agent-Lauf durchführen
6. prüfen, dass der Client erfolgreich berichtet
7. bestätigen, dass der Client in der LUMS-Oberfläche erscheint

Ein Client sollte nicht allein deshalb als operativ betrachtet werden, weil der Agent-Dienst erfolgreich startet.

Der Server muss einen gültigen Client-Bericht empfangen und akzeptieren.

---

## 21. Client-Status

Die Client-Ansicht sollte verwendet werden, um zwischen verschiedenen operativen Zuständen zu unterscheiden.

Beispiele sind:

* Client registriert, aber nicht berichtend
* Client berichtet normal
* Client berichtet veraltete Informationen
* Client deaktiviert
* Client-Authentifizierungsfehler
* clientseitiger Paketmanager-Fehler

Wenn ein Client aufhört zu berichten, stellen Sie zuerst fest, ob das Problem liegt in:

1. Netzwerkkonnektivität
2. TLS-Vertrauen
3. Client-Authentifizierung
4. Agent-Ausführung
5. Server-Verfügbarkeit
6. serverseitiger Verarbeitung

Vermeiden Sie es, Client-Anmeldeinformationen zu ändern, bevor Sie festgestellt haben, welche Schicht tatsächlich fehlschlägt.

---

## 22. Client-Token-Rotation

Client-Tokens können bei Bedarf rotiert werden.

Typische Gründe sind:

* vermutete Token-Exposition
* Credential-Rotationsrichtlinie
* administrative Wartung
* Ersatz einer Client-Konfiguration
* Reaktion auf einen Sicherheitsvorfall

Die Token-Rotation ändert das für den Client akzeptierte Credential.

Nach der Rotation:

1. den neuen Client-Token erhalten
2. die Client-Konfiguration aktualisieren
3. den Agent ausführen
4. erfolgreiche Authentifizierung prüfen
5. den resultierenden Client-Bericht prüfen
6. bestätigen, dass die normale Berichterstattung wieder aufgenommen wird

Entfernen Sie die alte Client-Konfiguration nicht, bis der neue Authentifizierungspfad verifiziert wurde.

---

## 23. Einen Client deaktivieren

Ein Client kann deaktiviert werden, wenn er nicht mehr an LUMS-Operationen teilnehmen soll.

Beispiele sind:

* Außerbetriebnahme des Systems
* vorübergehende Wartung
* Client-Ersatz
* vermutete Kompromittierung von Anmeldeinformationen

Prüfen Sie vor dem Deaktivieren eines Clients, ob aktive Update-Jobs damit verbunden sind.

Nach dem Deaktivieren:

* prüfen, dass der Client nicht mehr als operativ behandelt wird
* den relevanten Update-Job-Verlauf überprüfen
* Audit-Informationen erhalten, die für Untersuchungen erforderlich sind

Löschen Sie persistente Client-Daten nicht allein deshalb, weil ein Client vorübergehend offline ist.

---

## 24. Client-Administrationscheckliste

Beim Hinzufügen oder Ändern eines Clients prüfen Sie die vollständige Kette:

```text
[ ] Client exists in LUMS
[ ] Client is enabled
[ ] Client token is valid
[ ] TLS trust is valid
[ ] LUMS Agent is installed
[ ] Agent configuration is valid
[ ] Initial report succeeds
[ ] Client appears in the Web UI
[ ] Installed software is reported
[ ] Available updates are reported
[ ] Update jobs can be tracked
[ ] Results are returned correctly
```

Ein Client ist nur operativ, wenn die vollständige Berichterstattungs- und Authentifizierungskette funktioniert.

---

## 25. Administratives Prinzip

Benutzeradministration und Client-Administration sollten getrennt bleiben.

Ein LUMS-Anwendungskonto bestimmt, **was eine Person tun darf**.

Ein Client-Token bestimmt, **welches verwaltete System mit LUMS kommunizieren darf**.

```text
Application User
      │
      └── Role / Permissions

Managed Client
      │
      └── Client Token / Identity
```

Verwenden Sie einen Mechanismus nicht als Ersatz für den anderen.

## 26. Software-Inventar

LUMS pflegt Softwareinformationen, die von verwalteten Clients gemeldet werden.

Das Software-Inventar ermöglicht Administratoren und Operatoren festzustellen, welche Pakete auf einem Client installiert sind.

Das Inventar wird vom LUMS Agent gesammelt und an den Server gemeldet.

Der Server stellt die gemeldeten Informationen dann über die Client-Oberfläche bereit.

Das Inventar sollte als Momentaufnahme des vom Client gemeldeten Zustands behandelt werden.

Es ersetzt nicht den nativen Paketmanager.

---

## 27. Installierte Software

Der Bereich **Installierte Software** zeigt Pakete an, die vom ausgewählten Client gemeldet wurden.

Administratoren und Operatoren können den lokalen Paketfilter verwenden, um das angezeigte Inventar einzugrenzen.

Der Filter für installierte Software ist eine lokale Oberflächenfunktion.

Er ist von der Paketverwaltungssuche getrennt.

Diese Unterscheidung ist wichtig:

```text
Installed Software
    │
    └── Filter already reported package inventory

Package Management
    │
    └── Search the client's package repositories
```

Ein installiertes Paket erscheint daher möglicherweise nicht in der Paketverwaltungssuche, wenn es in einem konfigurierten Repository nicht mehr verfügbar ist.

---

## 28. Verfügbare Updates

LUMS sammelt außerdem Informationen über Pakete, für die Updates verfügbar sind.

Informationen über verfügbare Updates werden auf dem verwalteten Client mit seinem nativen Paketverwaltungssystem erzeugt.

Die gemeldeten Informationen können verwendet werden, um Pakete zu identifizieren, die Aufmerksamkeit erfordern.

Bevor Sie einen Update-Job erstellen, prüfen Sie:

* Client-Identität
* Paketname
* aktuell installierte Version
* verfügbare Version
* Paketstatus
* ob der Client derzeit erreichbar ist

Gehen Sie nicht davon aus, dass jedes verfügbare Update sofort installiert werden sollte.

Operative Anforderungen, Wartungsfenster, Anwendungsabhängigkeiten und Client-Zustand sollten vor der Ausführung berücksichtigt werden.

---

## 29. Paketverwaltung

LUMS bietet zentrale paketverwaltungsbezogene Operationen für unterstützte Linux-Clients.

Aktuelle paketverwaltungsbezogene Aktionen umfassen:

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

Die Operation wird über LUMS angefordert, aber lokal vom LUMS Agent ausgeführt.

Der Agent delegiert die tatsächliche Paketoperation an den nativen Paketmanager.

```text
LUMS Web UI
      │
      ▼
LUMS API
      │
      ▼
Update Job
      │
      ▼
LUMS Agent
      │
      ├── APT / dpkg
      │
      └── pacman
```

LUMS bleibt daher unabhängig von der Paketdatenbank und der Paketverwaltungsimplementierung des Betriebssystems.

---

## 30. Paketsuche

Die Oberfläche **Paketverwaltung** bietet eine Paketsuche, die vom Filter für installierte Software getrennt ist.

Die Suche fordert Paketinformationen vom verwalteten Client an.

Auf Debian-basierten Systemen verwendet der Agent die APT-Paketverwaltungswerkzeuge.

Auf Arch Linux verwendet der Agent `pacman`.

Suchergebnisse können enthalten:

* Paketname
* Paketversion
* Paketbeschreibung
* Repository-Informationen, wo verfügbar

Die Paketsuche installiert nichts.

Eine Suche ist daher eine schreibgeschützte Operation.

---

## 31. Ein Paket installieren

Administratoren und Operatoren können Paketinstallationsjobs erstellen.

Der normale Arbeitsablauf ist:

1. den verwalteten Client auswählen
2. **Paketverwaltung** öffnen
3. nach dem erforderlichen Paket suchen
4. das Ergebnis prüfen
5. die Installationsaktion auswählen
6. den Job erstellen
7. die Ausführung überwachen
8. das Ergebnis prüfen
9. die installierte Software aktualisieren oder erneut prüfen

Das Paket wird vom Agent mit dem nativen Paketmanager installiert.

Die erfolgreiche Erstellung des Jobs bedeutet nicht, dass die Installation bereits abgeschlossen ist.

Das endgültige Job-Ergebnis muss geprüft werden.

---

## 32. Ein Paket entfernen

Die Paketentfernung folgt demselben kontrollierten Job-Workflow.

Bevor Sie ein Paket entfernen, prüfen Sie:

* den korrekten Client
* das korrekte Paket
* die beabsichtigte Operation
* ob andere Software vom Paket abhängt

Prüfen Sie nach der Ausführung den resultierenden Job-Status und den gemeldeten Software-Zustand des Clients.

LUMS umgeht nicht die Abhängigkeitsbehandlung des Paketmanagers.

Der native Paketmanager bleibt für die Auflösung der Operation verantwortlich.

---

## 33. Ein Paket aktualisieren

Ein bestimmtes Paket kann aktualisiert werden, wenn ein Update verfügbar ist.

Der Arbeitsablauf ist:

```text
Available Update
      │
      ▼
Review Package
      │
      ▼
Create UPDATE_PACKAGE Job
      │
      ▼
Agent Execution
      │
      ▼
Result Validation
```

LUMS validiert die Paketinformationen, bevor der entsprechende Update-Job erstellt wird.

Wenn das Paket nicht mehr als aktualisierbar gelistet ist, sollte die Job-Anfrage nicht als gültige Update-Operation behandelt werden.

Dies verhindert, dass veraltete Update-Informationen blind ausgeführt werden.

---

## 34. Das System aktualisieren

`UPDATE_SYSTEM` führt ein umfassenderes Systemupdate mit dem nativen Paketverwaltungsmechanismus des Clients durch.

Diese Operation betrifft mehr als ein Paket und sollte daher als Wartungsoperation behandelt werden.

Bevor Sie ein Systemupdate starten, prüfen Sie:

* Client-Verfügbarkeit
* Wartungsfenster
* derzeit laufende Jobs
* Paketmanager-Zustand
* verfügbarer Festplattenplatz, wo relevant
* ob ein Reboot erforderlich sein könnte

Prüfen Sie nach dem Update:

* Job-Ergebnis
* Client-Bericht
* installierte Software
* verfügbare Updates
* Reboot-Zustand

---

## 35. Update-Jobs

Alle mutierenden Paket- und Update-Operationen werden als LUMS-Update-Jobs dargestellt.

Dies bietet ein gemeinsames Ausführungs- und Verfolgungsmodell.

Typischer Job-Lebenszyklus:

```text
PENDING
   │
   ▼
RUNNING
   │
   ├──────────────► FAILED
   │
   ▼
SUCCESS
```

Ein Job kann auch zusätzliche Behandlung erfordern, wenn der Client nicht verfügbar wird oder die Ausführung unterbrochen wird.

Der Job-Verlauf sollte als maßgebliche operative Aufzeichnung verwendet werden, anstatt sich ausschließlich auf die aktuelle Client-Ansicht zu verlassen.

---

## 36. Job-Erstellung

Bevor Sie einen Update-Job erstellen, prüfen Sie die beabsichtigte Operation sorgfältig.

Prüfen Sie:

* Client
* Aktion
* Paket
* Zielversion, wo zutreffend
* aktueller Paketzustand
* Wartungsanforderungen

Unterstützte Aktionen umfassen:

| Aktion            | Zweck                        |
| ----------------- | ---------------------------- |
| `INSTALL_PACKAGE` | Ein Paket installieren       |
| `REMOVE_PACKAGE`  | Ein Paket entfernen          |
| `UPDATE_PACKAGE`  | Ein bestimmtes Paket aktualisieren |
| `UPDATE_SYSTEM`   | Ein systemweites Update durchführen |

Die Erstellung von Update-Jobs ist auf die Rollen **Administrator** und **Operator** beschränkt.

Viewer können keine Update-Jobs erstellen.

---

## 37. Job-Ausführung

Nach der Erstellung wird der Job vom LUMS Agent verarbeitet.

Der Agent empfängt den Job und führt die angeforderte Operation lokal aus.

Der Server verfolgt den resultierenden Zustand.

Der Agent behandelt eine erfolgreiche HTTP-Anfrage nicht als Beweis dafür, dass die Paketoperation erfolgreich war.

Stattdessen wird das tatsächliche Paketmanager-Ergebnis an LUMS zurückgegeben.

Diese Unterscheidung ist wichtig:

```text
API request accepted
        ≠
Package operation successful
```

Das endgültige Ausführungsergebnis muss daher immer geprüft werden.

---

## 38. Job-Ergebnisse

Ein abgeschlossener Job sollte ein explizites Ergebnis enthalten.

Relevante Ergebnisse umfassen:

* erfolgreiche Ausführung
* fehlgeschlagene Ausführung
* Paketmanager-Fehler
* unterbrochene Ausführung
* wiederherstellungsbezogener Zustand
* reboot-bezogener Zustand, wo zutreffend

Administratoren und Operatoren sollten das Ergebnis prüfen, wenn ein Job fehlschlägt, anstatt die gleiche Operation sofort zu wiederholen.

Wiederholte Ausführung ohne Verständnis des ursprünglichen Fehlers kann die Diagnose erschweren.

---

## 39. Job-Verlauf

Der Update-Verlauf bietet eine operative Aufzeichnung früherer Update-Aktivitäten.

Verwenden Sie ihn, um Fragen zu beantworten wie:

* Wurde dieses Paket bereits aktualisiert?
* Welcher Client hat die Operation ausgeführt?
* Wann wurde der Job erstellt?
* Wann begann die Ausführung?
* Wann endete die Ausführung?
* War die Operation erfolgreich?
* Hat der Paketmanager einen Fehler gemeldet?

Historische Job-Informationen sind besonders wichtig bei der Untersuchung wiederholter Fehler oder unterbrochener Wartungsoperationen.

---

## 40. Fehlgeschlagene Jobs

Wenn ein Job fehlschlägt:

1. Client und Job-ID notieren
2. das Job-Ergebnis prüfen
3. feststellen, ob der Fehler auf dem Server oder Client aufgetreten ist
4. die relevanten Agent-Logs prüfen
5. den nativen Paketmanager-Zustand prüfen
6. das zugrunde liegende Problem beheben
7. erst wiederholen, nachdem die Ursache verstanden ist

Häufige Ursachen sind:

* nicht verfügbare Repositories
* Paketmanager-Sperren
* Netzwerkprobleme
* ungültige Paket-Anfragen
* Abhängigkeitskonflikte
* unzureichender Festplattenplatz
* unterbrochene Paketoperationen
* Client-Authentifizierungs- oder Kommunikationsprobleme

Detaillierte Diagnoseverfahren sind in `troubleshooting.md` dokumentiert.

---

## 41. Paketmanager-Sperren

APT und pacman können gleichzeitige Paketoperationen verhindern.

Wenn eine paketverwaltungsbezogene Operation fehlschlägt, weil der Paketmanager bereits verwendet wird:

* den aktiven Paketverwaltungsprozess identifizieren
* feststellen, welche Operation läuft
* auf das Ende der legitimen Operation warten, wenn angebracht
* die LUMS-Operation anschließend wiederholen

**Löschen Sie nicht blind Paketmanager-Lockdateien, während der Paketmanager läuft.**

Das Entfernen einer Lockdatei behebt nicht die zugrunde liegende gleichzeitige Operation und kann den Paketverwaltungszustand beschädigen.

---

## 42. Idle-bewusste Ausführung

LUMS kann Client-Idle-Informationen verwenden, um festzustellen, ob ein Update-Job ausgeführt werden sollte.

Dieser Mechanismus soll vermeiden, die aktive interaktive Nutzung eines verwalteten Systems zu unterbrechen.

Die Idle-Erkennung wird vom Agent auf dem Client durchgeführt.

Wenn Idle-Informationen nicht verfügbar sind, muss der Agent diesen Zustand melden, anstatt einen Idle-Zustand zu erfinden.

Administratoren sollten unterscheiden zwischen:

* Client ist idle
* Client ist aktiv
* Idle-Erkennung nicht verfügbar
* Client nicht erreichbar

Diese Zustände haben unterschiedliche operative Bedeutungen.

---

## 43. Überwachung der Update-Ausführung

Während der Wartung überwachen Sie:

* Job-Zustand
* Client-Konnektivität
* Agent-Aktivität
* Paketmanager-Ergebnis
* Reboot-Anforderung

Gehen Sie nicht davon aus, dass ein unbegrenzt im Zustand `RUNNING` verbleibender Job bedeutet, dass der Paketmanager noch arbeitet.

Wenn die Ausführung hängen zu bleiben scheint, untersuchen Sie den Client- und Agent-Zustand, bevor Sie einen weiteren Job erstellen.

---

## 44. Reboot-Anforderungen

Einige Paket- und Systemupdates können einen Reboot erfordern.

LUMS verfolgt reboot-bezogene Zustände, die vom verwalteten Client gemeldet werden.

Nach einem Systemupdate:

1. den gemeldeten Reboot-Zustand prüfen
2. feststellen, ob ein Reboot erforderlich ist
3. den Reboot während eines geeigneten Wartungsfensters durchführen
4. dem Agent erlauben, erneut zu berichten
5. prüfen, dass der Client zum normalen Betrieb zurückkehrt

Eine Reboot-Anforderung sollte nicht automatisch als Update-Fehler interpretiert werden.

---

## 45. Operative Update-Checkliste

Für routinemäßige Paketwartung:

```text
[ ] Correct client selected
[ ] Client is reachable
[ ] Current software state reviewed
[ ] Available updates reviewed
[ ] Correct package/action selected
[ ] Maintenance requirements checked
[ ] Update job created
[ ] Job execution monitored
[ ] Job result verified
[ ] Installed software verified
[ ] Available updates rechecked
[ ] Reboot state checked
[ ] Job history reviewed if required
```

Die Operation ist erst abgeschlossen, nachdem der resultierende Client-Zustand verifiziert wurde.

---

## 46. Paketverwaltungsprinzip

LUMS bietet zentrale Orchestrierung und Sichtbarkeit.

Das verwaltete Betriebssystem bleibt für die tatsächliche Paketverwaltung verantwortlich.

Daher:

> **LUMS fordert die Operation an und verfolgt sie. Der native Paketmanager führt sie aus.**

Diese Trennung ermöglicht es LUMS, verschiedene Linux-Systeme zu verwalten, während die Paketverwaltungssemantik jedes Betriebssystems erhalten bleibt.

## 47. Job-Wiederherstellung

LUMS ist darauf ausgelegt, unterbrochene Update-Jobs zu behandeln, ohne Operationen blind zu wiederholen, die bereits erfolgreich abgeschlossen wurden.

Die Update-Ausführung verwendet Checkpoint-Informationen, um den Fortschritt zu verfolgen.

Dies ist besonders wichtig, wenn:

* der Agent unterbrochen wird
* der Client neu bootet
* der Server neu gestartet wird
* Netzwerkkommunikation vorübergehend nicht verfügbar ist
* eine Paketoperation abgeschlossen wird, bevor das Ergebnis gemeldet wird

Der Wiederherstellungsmechanismus verwendet den aufgezeichneten Job-Zustand, um festzustellen, welche Arbeit noch ausgeführt werden muss.

---

## 48. Paket-Level-Checkpointing

Jobs, die mehrere Paketoperationen enthalten, werden einzeln verarbeitet.

Eine erfolgreiche Paketoperation wird aufgezeichnet, bevor der Agent mit der nächsten Operation fortfährt.

Konzeptionell:

```text
Job
 │
 ├── Package A → SUCCESS
 │
 ├── Package B → SUCCESS
 │
 ├── Package C → interrupted
 │
 └── Package D → PENDING
```

Nach der Wiederherstellung sollten bereits abgeschlossene Paketoperationen nicht unnötig erneut ausgeführt werden.

Die verbleibende Arbeit kann dann vom aufgezeichneten Zustand aus fortgesetzt werden.

Dies reduziert das Risiko, Paketoperationen nach einer Unterbrechung zu wiederholen.

---

## 49. Unterbrochene Jobs

Wenn ein Update-Job unterbrochen wird, erstellen Sie nicht sofort einen Ersatzjob.

Stellen Sie zuerst fest:

1. welcher Job unterbrochen wurde
2. welche Paketoperation aktiv war
3. welche Paketoperationen bereits erfolgreich waren
4. ob der Paketmanager die Operation abgeschlossen hat
5. ob der Agent den Job automatisch wiederhergestellt hat
6. ob der Client einen Reboot erfordert

Der vorhandene Job-Verlauf und die Agent-Logs sollten vor manuellem Eingreifen untersucht werden.

---

## 50. Agent-Wiederherstellung

Der Agent ist verantwortlich für die Fortsetzung wiederherstellbarer Arbeit nach einer Unterbrechung.

Die Wiederherstellung sollte erfolgreiche Paketergebnisse wo immer möglich erhalten.

Wenn eine Paketoperation bereits als erfolgreich aufgezeichnet ist, darf die Wiederherstellung dieselbe Operation nicht blind erneut ausführen.

Wenn die Wiederherstellung den Zustand einer Operation nicht sicher bestimmen kann, sollte der Zustand als operatives Problem behandelt und untersucht werden.

Ändern Sie Job-Zustände in der Datenbank nicht manuell, nur damit ein Job als abgeschlossen erscheint.

---

## 51. Server-Neustart während eines Jobs

Ein Neustart des LUMS-Servers bedeutet nicht zwangsläufig, dass die clientseitige Paketoperation unterbrochen wurde.

Server und Client haben getrennte Ausführungszustände.

Nach einem Server-Neustart:

1. prüfen, dass der LUMS-Container läuft
2. Datenbankverfügbarkeit prüfen
3. prüfen, dass der Client mit LUMS kommunizieren kann
4. betroffene Update-Jobs prüfen
5. Agent-Berichte prüfen
6. den endgültigen Paketzustand prüfen

Das clientseitige Ausführungsergebnis bleibt die wichtige Quelle der Wahrheit für die Paketoperation.

---

## 52. Client-Neustart während eines Jobs

Ein Client-Neustart kann die Agent-Ausführung unterbrechen oder auftreten, weil das Update selbst einen Reboot erfordert.

Diese Situationen müssen unterschieden werden.

### Erwarteter Reboot

Das Update wurde abgeschlossen und das System erfordert einen Reboot.

### Unerwartete Unterbrechung

Das System wurde neu gestartet, bevor die Operation abgeschlossen war oder bevor das Ergebnis gemeldet werden konnte.

Nachdem der Client zurückkehrt:

1. dem Agent erlauben, normal zu starten
2. Kommunikation mit LUMS prüfen
3. den betroffenen Job prüfen
4. Paketzustand prüfen
5. Reboot-Status prüfen
6. der Wiederherstellung erlauben, fortzufahren, wo anwendbar

---

## 53. Reboot-Erkennung

LUMS kann Reboot-Anforderungen verfolgen, die vom verwalteten Client gemeldet werden.

Reboot-Erkennung ist nicht dasselbe wie das Erkennen, ob die Maschine derzeit erreichbar ist.

Dies sind getrennte Zustände:

```text
Client reachable
        │
        ├── reboot not required
        │
        └── reboot required

Client unreachable
        │
        └── current state cannot be confirmed
```

Administratoren sollten daher vermeiden, einen nicht erreichbaren Client als Beweis dafür zu behandeln, dass ein Reboot erforderlich ist.

---

## 54. Verifikation nach dem Reboot

Nach einem erforderlichen Reboot:

1. warten, bis das Betriebssystem verfügbar ist
2. den Agent-Dienst oder -Timer prüfen
3. Client-Authentifizierung prüfen
4. den Client-Bericht prüfen
5. den betroffenen Update-Job prüfen
6. installierte Paketversionen prüfen
7. verfügbare Updates prüfen
8. prüfen, ob ein weiterer Reboot erforderlich ist

Ein Reboot sollte erst als operativ abgeschlossen betrachtet werden, nachdem der Client erfolgreich erneut berichtet hat.

---

## 55. Überwachung von Update-Jobs

Administratoren und Operatoren sollten Jobs während geplanter Wartung überwachen.

Wichtige Zustände sind:

| Zustand   | Bedeutung                                          |
| --------- | -------------------------------------------------- |
| `PENDING` | Job existiert, aber die Ausführung hat nicht begonnen |
| `RUNNING` | Job-Ausführung ist in Bearbeitung                  |
| `SUCCESS` | Ausführung erfolgreich abgeschlossen               |
| `FAILED`  | Ausführung mit einem Fehler abgeschlossen          |

Ein Job-Zustand sollte immer zusammen mit seinen Ergebnisinformationen interpretiert werden.

Zum Beispiel sollte ein `FAILED`-Job anhand seines aufgezeichneten Ergebnisses untersucht werden, anstatt ihn einfach zu wiederholen.

---

## 56. Execution Watcher

Der LUMS Agent enthält einen dedizierten Execution Watcher.

Der Watcher ist verantwortlich für die Überwachung der Update-Job-Ausführung auf dem Client.

Sein Zweck ist es, zuverlässige Ausführungsbehandlung unabhängig vom Berichterstattungs-Workflow zu unterstützen.

Die aktuelle Watcher-Version ist:

**Watcher 1.2.1**

Die Agent-Version ist:

**Agent 1.7.0**

Diese Versionen sollten nach Client-Upgrades geprüft werden.

---

## 57. Watcher-Überwachung

Administratoren können den Watcher über systemd auf dem verwalteten Client inspizieren.

Nützliche Prüfungen umfassen:

```bash
systemctl status lums-agent-watcher.service --no-pager
```

und:

```bash
journalctl -u lums-agent-watcher.service --no-pager -n 100
```

Der Timer kann inspiziert werden mit:

```bash
systemctl status lums-agent-watcher.timer --no-pager
```

Der exakte aktiv/inaktiv-Zustand eines Oneshot-Dienstes sollte zusammen mit seinem Timer und Journal interpretiert werden.

Ein `inactive (dead)`-Zustand ist für einen Oneshot-Dienst nicht automatisch ein Fehler.

---

## 58. Reporting- und Ausführungs-Timer

LUMS trennt die reguläre Client-Berichterstattung von der Ausführungsüberwachung.

Der Reporting-Timer ist für die geplante Agent-Ausführung verantwortlich.

Der Watcher-Timer ist für die geplante Watcher-Ausführung verantwortlich.

Inspizieren Sie beide bei der Diagnose clientseitiger Planungsprobleme:

```bash
systemctl list-timers --all | grep lums-agent
```

Erwartete Units umfassen:

```text
lums-agent.timer
lums-agent-watcher.timer
```

Wenn ein Timer nicht läuft, inspizieren Sie:

```bash
systemctl status lums-agent.timer --no-pager
systemctl status lums-agent-watcher.timer --no-pager
```

Inspizieren Sie dann die entsprechenden Journal-Einträge.

---

## 59. Audit-Logging

LUMS zeichnet wichtige administrative und sicherheitsrelevante Anwendungsaktionen im Audit-Log auf.

Audit-Informationen können helfen festzustellen:

* welche Operation aufgetreten ist
* welcher Benutzer sie initiiert hat
* welcher Client betroffen war
* wann die Operation aufgetreten ist
* ob die Operation akzeptiert wurde
* welche administrative Aktion durchgeführt wurde

Audit-Informationen sollten als operativer Nachweis behandelt werden.

Sie sollten nicht beiläufig gelöscht oder verändert werden.

---

## 60. Administrative Audit-Ereignisse

Relevante administrative Aktivität umfasst Operationen wie:

* Benutzererstellung
* Rollenzuweisung
* Client-Verwaltung
* Token-Rotation
* Erstellung von Update-Jobs
* paketverwaltungsbezogene Operationen
* authentifizierungsbezogene Sicherheitsereignisse

Die genauen Ereignisdaten hängen von der Operation ab.

Administratoren sollten Audit-Informationen zusammen mit dem Job-Verlauf verwenden, wenn sie unerwartete Aktivität untersuchen.

---

## 61. Umgang mit Audit-Logs

Audit-Logs sollten sorgfältig behandelt werden.

Nicht:

* historische Audit-Einträge ändern, um eine Operation zu verbergen
* sensible Anmeldeinformationen in exportierten Logs preisgeben
* Logs veröffentlichen, die Client-Tokens enthalten
* Passwörter oder Authentifizierungsmaterial veröffentlichen
* sensible Log-Ausgabe in öffentliche Issue-Tracker kopieren

Wenn Logs zur Fehlerbehebung geteilt werden müssen, schwärzen Sie zuerst Anmeldeinformationen und andere sensible Informationen.

---

## 62. Anwendungslogs

Anwendungslogs beschreiben den internen Betrieb des LUMS-Servers.

Nützliche Quellen umfassen:

```bash
sudo docker logs --tail 100 lums
```

Für Live-Überwachung:

```bash
sudo docker logs -f lums
```

Beschränken Sie bei der Untersuchung eines Problems das Zeitfenster, wo möglich.

Geben Sie nicht automatisch das gesamte Produktionslog aus, wenn ein kleinerer relevanter Abschnitt ausreichend ist.

---

## 63. Agent-Logs

Clientseitige Agent-Aktivität kann über systemd inspiziert werden:

```bash
journalctl -u lums-agent.service --no-pager -n 100
```

Für Watcher-Aktivität:

```bash
journalctl -u lums-agent-watcher.service --no-pager -n 100
```

Für ein bestimmtes Zeitfenster kann die systemd-Journal-Filterung verwendet werden.

Beispiel:

```bash
journalctl -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

Logs sollten, wo möglich, mit der betroffenen Job-ID korreliert werden.

---

## 64. Log-Korrelation

Bei der Untersuchung eines Update-Problems korrelieren Sie Informationen über das System hinweg:

```text id="jv3j7c"
Web UI
  │
  ├── Job ID
  │
  ▼
LUMS API / Application Log
  │
  ▼
Update Job
  │
  ▼
Agent
  │
  ▼
Native Package Manager
```

Dies verhindert den häufigen Fehler anzunehmen, dass ein in einer Schicht beobachtetes Problem in derselben Schicht entstanden ist.

---

## 65. Administrative Überwachungscheckliste

Prüfen Sie während des normalen Betriebs regelmäßig:

```text
[ ] LUMS container is running
[ ] HTTPS endpoint is available
[ ] Database is accessible
[ ] Clients are reporting
[ ] No unexpected failed jobs
[ ] No unexplained authentication failures
[ ] Agent timers are active
[ ] Watcher timers are active
[ ] Package-manager operations complete normally
[ ] Audit activity is available
[ ] Logs contain no unexplained recurring errors
```

Die Häufigkeit dieser Prüfungen sollte der operativen Bedeutung der LUMS-Bereitstellung entsprechen.

---

## 66. Wiederherstellungsprinzip

Wenn ein Update-Problem auftritt, ist der sicherste administrative Ansatz:

```text
Observe
   │
   ▼
Identify affected job/client
   │
   ▼
Inspect state and logs
   │
   ▼
Determine actual failure point
   │
   ▼
Correct underlying problem
   │
   ▼
Allow recovery or retry
   │
   ▼
Verify final state
   │
   ▼
Document significant incidents
```

Vermeiden Sie destruktive Wiederherstellungsaktionen, es sei denn, der tatsächliche Fehlerzustand ist verstanden.

Insbesondere dürfen Sie nicht manuell Jobs, Datenbankeinträge, Paketmanager-Sperren oder persistente Client-Daten löschen, nur um eine sauber aussehende Oberfläche wiederherzustellen.

> **Zuerst Beweise sichern. Zweitens den Zustand reparieren. Drittens das Ergebnis verifizieren.**

## 67. Datenbank-Administration

LUMS verwendet SQLite als Anwendungsdatenbank.

Die Produktionsdatenbank wird im persistenten Docker-Volume gespeichert:

```text
/var/lib/lums/lums.db
```

Die Datenbank ist über den Container-Austausch hinweg persistent, solange das Docker-Volume erhalten bleibt.

Die Datenbank enthält Anwendungszustand wie:

* Benutzer
* verwaltete Clients
* Update-Jobs
* Paketinformationen
* Audit-Informationen
* authentifizierungsbezogener Zustand
* Migrationszustand

Administratoren sollten die Datenbank als kritische Anwendungsdaten behandeln.

---

## 68. SQLite-Laufzeitkonfiguration

Die aktuelle SQLite-Produktionsbasis ist:

| Einstellung    | Wert                        |
| -------------- | --------------------------- |
| `journal_mode` | `wal`                       |
| `busy_timeout` | `5000`                      |
| `synchronous`  | `2`                         |
| `foreign_keys` | von der Anwendung aktiviert |

Die Anwendung aktiviert ausdrücklich die SQLite-Fremdschlüssel-Durchsetzung für Datenbankverbindungen.

Administratoren sollten diese Einstellungen nicht beiläufig ändern.

Änderungen der Datenbank-Laufzeitkonfiguration sollten getestet werden, bevor sie in die Produktion eingeführt werden.

---

## 69. Datenbankintegrität

Die Datenbankintegrität sollte geprüft werden, wenn Anzeichen für Datenbankbeschädigung oder unerwartetes Anwendungsverhalten vorliegen.

Eine typische SQLite-Integritätsprüfung ist:

```bash id="f0g8sl"
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "PRAGMA integrity_check;"
```

Eine gesunde Datenbank sollte zurückgeben:

```text
ok
```

Wenn die Integritätsprüfung Fehler meldet, fahren Sie nicht fort, den Anwendungszustand blind zu verändern.

Bewahren Sie die betroffene Datenbank auf und untersuchen Sie die Ursache.

---

## 70. Datenbankmigrationen

LUMS verwendet Anwendungsmigrationen, um Datenbankänderungen einzuführen.

Migrationen sollten über den normalen Start- und Migrationsmechanismus der Anwendung laufen gelassen werden.

Administratoren sollten den Migrationszustand nicht manuell ändern, nur um einen Fehler zu umgehen.

Prüfen Sie nach einem Anwendungsupdate:

1. der Container startet erfolgreich
2. Migrationen werden abgeschlossen
3. die Anwendung ist erreichbar
4. bestehende Benutzer bleiben verfügbar
5. bestehende Clients bleiben verfügbar
6. bestehender Job-Verlauf bleibt verfügbar

---

## 71. Persistentes Docker-Volume

Das Docker-Volume, das LUMS-Anwendungsdaten enthält, ist eine kritische persistente Ressource.

Das Produktions-Volume ist:

```text
lums-data
```

Inspizieren Sie es mit:

```bash id="f3z2kd"
sudo docker volume inspect lums-data
```

Das Volume muss beim Ersetzen des LUMS-Containers angehängt bleiben.

Das Entfernen des Containers entfernt das Volume **nicht** automatisch.

Das Entfernen des Volumes entfernt jedoch die persistenten Anwendungsdaten dauerhaft, es sei denn, ein separates Backup existiert.

---

## 72. Container-Administration

Die LUMS-Anwendung läuft in einem gehärteten Docker-Container.

Die Produktions-Sicherheitsbasis umfasst:

* Non-Root-Anwendungsbenutzer
* schreibgeschütztes Root-Dateisystem
* verworfene Linux-Capabilities
* `no-new-privileges`
* eingeschränkte temporäre Dateisysteme
* schreibgeschützter Secret-Mount
* dediziertes persistentes Daten-Volume
* Anwendungsport nur auf localhost

Der Container sollte nicht mit schwächeren Sicherheitseinstellungen gestartet werden, nur weil die Fehlerbehebung bequemer wird.

---

## 73. Container-Status

Prüfen Sie den aktuellen Containerzustand mit:

```bash id="4n6p2v"
sudo docker ps --filter name=lums
```

Inspizieren Sie die vollständige Laufzeitkonfiguration mit:

```bash id="k1q4z8"
sudo docker inspect lums
```

Wichtige Eigenschaften umfassen:

* Laufzustand
* Restart-Richtlinie
* Benutzer
* schreibgeschütztes Root-Dateisystem
* Capabilities
* Sicherheitsoptionen
* Port-Bindungen
* Volume-Mounts

---

## 74. Container-Sicherheitsverifikation

Die gehärtete Laufzeit sollte weiterhin die erwarteten Eigenschaften bieten.

Zum Beispiel:

```bash id="0u7x3n"
sudo docker inspect lums \
    --format '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.Privileged}}'
```

Die erwartete Basis ist äquivalent zu:

```text
lums true false
```

Capabilities sollten verworfen bleiben:

```bash id="k5n8ae"
sudo docker inspect lums \
    --format '{{json .HostConfig.CapDrop}}'
```

Erwartet:

```text
["ALL"]
```

Sicherheitsoptionen sollten umfassen:

```text
no-new-privileges:true
```

---

## 75. Anwendungsport

Die LUMS-Anwendung lauscht auf dem Host über die Loopback-Schnittstelle.

Die erwartete Zuordnung ist:

```text
127.0.0.1:5050 → container:5000
```

Prüfen Sie sie mit:

```bash id="b6v2w0"
sudo docker port lums
```

Der Anwendungsport sollte nicht direkt dem LAN ausgesetzt sein.

Externer Zugriff wird über Nginx über HTTPS bereitgestellt.

---

## 76. Nginx und HTTPS

Nginx bietet den externen HTTPS-Einstiegspunkt für LUMS.

Der normale Anfragepfad ist:

```text
Client Browser
      │
      ▼
HTTPS :443
      │
      ▼
Nginx
      │
      ▼
127.0.0.1:5050
      │
      ▼
LUMS Container
```

Der Docker-Anwendungsport sollte auf localhost beschränkt bleiben.

Administratoren sollten daher vermeiden, Port `5050` direkt über die Firewall oder Docker-Konfiguration freizugeben.

---

## 77. HTTPS-Verifikation

Validieren Sie nach Nginx-Änderungen immer die Konfiguration, bevor Sie neu laden:

```bash id="7f1h9m"
sudo nginx -t
```

Wenn die Konfiguration gültig ist:

```bash id="4g5s2w"
sudo systemctl reload nginx
```

Prüfen Sie dann HTTPS:

```bash id="2w8v6c"
curl -I https://LUMS-SERVER/
```

Ersetzen Sie `LUMS-SERVER` durch den Hostnamen, der vom TLS-Zertifikat des Servers abgedeckt ist. Verwenden Sie `-k` nicht für routinemäßige Verifikation; es überspringt die Zertifikatsvalidierung.

Eine erfolgreiche HTTPS-Antwort bestätigt, dass Nginx die LUMS-Anwendung erreichen kann.

Die Zertifikatsvalidierung sollte auch mit dem Hostnamen oder der Adresse getestet werden, die Administratoren normalerweise verwenden.

Deaktivieren Sie die Zertifikatsverifikation nicht dauerhaft mit `-k`.

---

## 78. HTTP-Weiterleitung

Der HTTP-Endpunkt sollte Clients auf HTTPS weiterleiten.

Prüfen Sie:

```bash id="w5q0rx"
curl -I http://127.0.0.1/
```

Das erwartete Verhalten ist eine HTTP-Weiterleitung zum HTTPS-Endpunkt.

Administrativer Zugriff sollte HTTPS verwenden.

---

## 79. TLS-Zertifikatswartung

TLS-Zertifikate und private Schlüssel sind extern zum Docker-Image.

Typische Speicherorte sind:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Private Schlüssel müssen geschützt bleiben.

Vor dem Ersetzen eines Zertifikats:

1. das neue Zertifikat prüfen
2. den passenden privaten Schlüssel prüfen
3. Dateiberechtigungen prüfen
4. die Nginx-Konfiguration validieren
5. Nginx neu laden
6. HTTPS prüfen
7. Anwendungs-Login prüfen

Legen Sie private TLS-Schlüssel niemals im Git-Repository oder Docker-Image ab.

---

## 80. Secret-Verwaltung

Das Anwendungssecret wird außerhalb des Container-Images gespeichert.

Das Produktionssecret wird schreibgeschützt in den Container gemountet:

```text
/etc/lums/secrets/lums_secret
        │
        ▼
/run/secrets/lums_secret
```

Die Anwendung erhält das Secret über:

```text
LUMS_SECRET_KEY_FILE
```

Administratoren dürfen niemals:

* das Secret committen
* das Secret ausgeben
* das Secret in die Dokumentation aufnehmen
* es in Screenshots preisgeben
* es in eine Image-Schicht legen

Wenn vermutet wird, dass das Secret preisgegeben wurde, behandeln Sie es als kompromittiert und folgen Sie dem entsprechenden Secret-Rotationsverfahren.

---

## 81. Backup-Strategie

LUMS-Daten sollten vor signifikanten administrativen Änderungen gesichert werden.

Berücksichtigen Sie mindestens den Schutz von:

* SQLite-Anwendungsdaten
* Anwendungskonfiguration
* TLS-Material
* Anwendungssecrets
* Client-Konfigurationsinformationen
* relevante operative Dokumentation

Backups sollten getrennt vom Produktionscontainer und seinem persistenten Docker-Volume gespeichert werden.

Ein Backup, das nur innerhalb desselben Hosts oder Docker-Volumes existiert, bietet keinen ausreichenden Schutz gegen den Verlust dieses Hosts oder Volumes.

---

## 82. Datenbank-Backup

Die SQLite-Datenbank sollte mit einer SQLite-bewussten Methode gesichert werden, anstatt eine aktiv veränderte Datenbankdatei einfach ohne Berücksichtigung ihres Zustands zu kopieren.

Bevor Sie ein Backup durchführen:

1. die Produktionsdatenbank identifizieren
2. sicherstellen, dass das Backup-Ziel verfügbar ist
3. das Backup mit einer geeigneten SQLite-sicheren Methode erstellen
4. prüfen, dass das Backup existiert
5. aufzeichnen, wann es erstellt wurde

Gehen Sie nicht davon aus, dass eine erfolgreiche Dateikopie automatisch bedeutet, dass ein gültiges wiederherstellbares Datenbank-Backup existiert.

---

## 83. Backup-Verifikation

Ein Backup gilt erst als zuverlässig, wenn es getestet wurde.

Prüfen Sie regelmäßig, dass ein Backup:

* gelesen werden kann
* als SQLite-Daten geöffnet werden kann
* auf Integrität geprüft werden kann
* in eine isolierte Testumgebung wiederhergestellt werden kann

Zum Beispiel kann eine extrahierte Testkopie geprüft werden mit:

```bash id="p3v7cx"
sqlite3 /path/to/test-copy.db \
    "PRAGMA integrity_check;"
```

Erwartetes Ergebnis:

```text
ok
```

Ein Produktionsbackup sollte niemals getestet werden, indem die aktive Produktionsdatenbank überschrieben wird.

---

## 84. Wiederherstellungsprinzip

Die Wiederherstellung ist eine kontrollierte administrative Operation.

Vor der Wiederherstellung:

1. das korrekte Backup identifizieren
2. seine Integrität prüfen
3. den erforderlichen Wiederherstellungspunkt bestimmen
4. Anwendungsaktivität stoppen oder isolieren, wie angebracht
5. den aktuellen Produktionszustand bewahren
6. das Backup wiederherstellen
7. Datenbankintegrität prüfen
8. die Anwendung starten
9. Migrationen prüfen
10. Benutzer und Clients prüfen
11. Job-Verlauf prüfen
12. normale Client-Berichterstattung prüfen

Überschreiben Sie während der Wiederherstellung nicht die einzige Kopie der Produktionsdatenbank.

---

## 85. Wiederherstellungsverifikation

Prüfen Sie nach einer Wiederherstellung mindestens:

```text id="q6r2yh"
[ ] Container starts
[ ] Database opens
[ ] SQLite integrity check passes
[ ] Users are present
[ ] Roles are correct
[ ] Clients are present
[ ] Client authentication works
[ ] Job history is present
[ ] Audit information is available
[ ] HTTPS works
[ ] Clients can report
[ ] New operations can be created
```

Eine Wiederherstellung ist erst abgeschlossen, nachdem die Anwendung und ihre verwalteten Clients verifiziert wurden.

---

## 86. Server-Backup-Prinzip

Die wichtigste administrative Regel für persistente LUMS-Daten ist:

> **Führen Sie niemals eine destruktive Datenbank- oder Volume-Operation ohne einen verifizierten Wiederherstellungspfad durch.**

Insbesondere dürfen Sie `lums-data` nicht entfernen, nur weil der Container neu gebaut oder ersetzt wird.

Container-Ersatz und Löschung persistenter Daten sind getrennte Operationen.

---

## 87. Administrative Server-Checkliste

Bevor Sie eine signifikante serverseitige Änderung durchführen:

```text id="7h3m0p"
[ ] Current container state recorded
[ ] Current image recorded
[ ] Database backup available
[ ] Backup integrity verified
[ ] Active jobs reviewed
[ ] Client reporting state reviewed
[ ] Configuration changes documented
[ ] TLS material available
[ ] Secret handling verified
[ ] Rollback path known
```

Erst nachdem diese Bedingungen berücksichtigt wurden, sollte eine signifikante Produktionsänderung fortgesetzt werden.

---

## 88. Server-Administrationsprinzip

LUMS trennt Anwendungszustand vom wegwerfbaren Anwendungscontainer.

```text
Disposable
└── LUMS Container

Persistent
├── SQLite Database
└── lums-data Volume

External
├── TLS Material
└── Application Secret
```

Diese Trennung ermöglicht es, den Anwendungscontainer zu ersetzen, ohne absichtlich persistente Anwendungsdaten zu zerstören.

> **Ersetzen Sie die Anwendung, wenn nötig. Bewahren Sie die Daten, es sei denn, Datenlöschung ist ausdrücklich beabsichtigt.**

## 89. Routinewartung

Routinewartung hält die LUMS-Installation zuverlässig und reduziert das Risiko unerwarteter operativer Probleme.

Typische Wartungsaktivitäten umfassen:

* Überprüfung fehlgeschlagener Update-Jobs
* Prüfung der Client-Berichterstattung
* Überprüfung der Anwendungslogs
* Überprüfung der Audit-Aktivität
* Verifikation von Backups
* Prüfung des verfügbaren Festplattenplatzes
* Überprüfung des Docker-Containerzustands
* Prüfung der Gültigkeit von TLS-Zertifikaten
* Überprüfung von Sicherheitsupdates
* Verifikation der aktuellen LUMS-Version und des Images

Wartung sollte während eines geeigneten Wartungsfensters durchgeführt werden, wenn Änderungen Produktionsclients beeinflussen können.

---

## 90. Wartung vor Änderungen

Bevor Sie Wartung durchführen, die den LUMS-Server beeinflussen kann:

1. aktive Update-Jobs prüfen
2. prüfen, dass Clients keine unerwartete Wartung durchlaufen
3. ein aktuelles Backup erstellen oder verifizieren
4. den aktuellen Container- und Image-Zustand aufzeichnen
5. die geplante Änderung dokumentieren
6. sicherstellen, dass ein Rollback-Pfad existiert

Beginnen Sie die Wartung nicht damit, sofort Produktionskomponenten zu stoppen oder zu löschen.

Stellen Sie zuerst den aktuellen Zustand fest.

---

## 91. Docker-Image-Wartung

LUMS-Anwendungsimages sollten aus dem überprüften Quellbaum neu gebaut werden.

Vor dem Bauen eines neuen Images:

```bash id="x0m7r4"
cd /opt/lums-public
```

Führen Sie die automatisierte Testsuite aus:

```bash id="4gk1dp"
./.venv-test/bin/pytest -q
```

Fahren Sie erst fort, wenn das Testergebnis verstanden ist.

Bauen Sie das neue Image mit einem separaten temporären Tag:

```bash id="m8q3vz"
sudo docker build -t lums:new .
```

Ein temporäres Tag ermöglicht es, das aktuell laufende Image während des Ersetzungsprozesses identifizierbar zu halten.

---

## 92. Image-Verifikation

Prüfen Sie nach dem Bauen eines neuen Images, dass das Image existiert:

```bash id="h6s2we"
sudo docker image inspect lums:new
```

Überprüfen Sie die Image-Konfiguration vor der Bereitstellung.

Prüfen Sie, wo angebracht:

* Image-Digest
* Basisimage
* Anwendungsdateien
* installierte Abhängigkeiten
* Image-Größe
* exponierte Ports
* konfigurierter Benutzer

Das Image sollte erst bereitgestellt werden, nachdem die Build- und Testergebnisse überprüft wurden.

---

## 93. Kontrollierter Container-Austausch

Der Container-Austausch sollte bewusst durchgeführt werden.

Bevor Sie den Produktionscontainer ersetzen:

```text id="m3z8qk"
[ ] Tests passed
[ ] New image exists
[ ] Database backup available
[ ] Active jobs reviewed
[ ] Current image recorded
[ ] Persistent volume confirmed
[ ] Secret available
[ ] TLS configuration available
[ ] Rollback image identified
```

Bevor Sie das Beispiel ausführen, vergleichen Sie es mit dem tatsächlich laufenden Container. Die folgenden Werte sind ein Beispiel, kein Befehl, der für jede Installation sicher ist. Insbesondere müssen Docker-Bind-Mount-Quellpfade auf der linken Seite von `:` zu Ihrem Host passen, und der alte Container kann einen anderen Namen haben.

Zeigen Sie Image, Mounts, veröffentlichte Ports, Restart-Richtlinie und Härtungseinstellungen an, ohne Umgebungsvariablenwerte auszugeben:

```bash
sudo docker inspect lums --format 'Image={{.Config.Image}}
Mounts={{json .Mounts}}
Ports={{json .HostConfig.PortBindings}}
Restart={{json .HostConfig.RestartPolicy}}
Readonly={{.HostConfig.ReadonlyRootfs}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
Tmpfs={{json .HostConfig.Tmpfs}}'
```

Speichern Sie die Ausgabe an einem privaten Ort und verwenden Sie sie, um zu prüfen, dass der neue Container dasselbe Datenbank-Volume, dieselbe Secret-Datei, dasselbe Backup-Verzeichnis, dieselbe Local-Only-Port-Bindung und dieselben Sicherheitsoptionen beibehält. Fügen Sie keine Secret-Inhalte oder Umgebungsvariablenwerte in Notizen oder Nachrichten ein.

Stoppen Sie den bestehenden Container erst, nachdem diese Bedingungen berücksichtigt wurden.

Der Produktionscontainer sollte die gehärtete Laufzeitkonfiguration beibehalten.

Beispiel:

```bash id="n8q2kf"
sudo docker stop lums
sudo docker rename lums lums-before-upgrade
```

Starten Sie dann das neue Image mit der etablierten gehärteten Konfiguration:

```bash id="c7w4md"
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
    -v /var/backups/lums:/var/backups/lums \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    -e LUMS_BACKUP_DIR=/var/backups/lums \
    lums:new
```

Entfernen Sie `lums-before-upgrade` nicht, bis die neue Bereitstellung validiert wurde.

---

## 94. Post-Upgrade-Validierung

Prüfen Sie unmittelbar nach dem Ersetzen des Containers:

```bash id="b4m7tz"
sudo docker ps --filter name=lums
```

Inspizieren Sie dann die Logs:

```bash id="v5n2ra"
sudo docker logs --tail 100 lums
```

Prüfen Sie HTTPS:

```bash id="w9x1kf"
curl -I https://LUMS-SERVER/
```

Ersetzen Sie `LUMS-SERVER` durch den Hostnamen, der vom TLS-Zertifikat des Servers abgedeckt ist. Verwenden Sie `-k` nicht für routinemäßige Verifikation; es überspringt die Zertifikatsvalidierung.

Prüfen Sie dann die Anwendung über die normale administrative Oberfläche.

Prüfen Sie, dass bestehende Benutzer, Clients und der aktuelle Verlauf weiterhin vorhanden sind. Überprüfen Sie die Logs auf Start- oder Migrationsfehler. Ein laufender Container allein beweist nicht, dass die Anwendung oder ihre Datenbank gesund ist.

### Rollback, wenn der neue Container nicht funktioniert

Behalten Sie den alten Container, bis die neue Version die Validierung bestanden hat. Wenn der neue Container unbrauchbar ist und Sie bestätigt haben, dass der alte Container `lums-before-upgrade` heißt, stoppen und entfernen Sie **nur den neuen Container**, dann benennen Sie den alten um und starten Sie ihn:

```bash
sudo docker stop lums
sudo docker rm lums
sudo docker rename lums-before-upgrade lums
sudo docker start lums
```

`docker rm lums` ohne `-v` entfernt den Container, nicht das Volume `lums-data`. Fügen Sie diesem Rollback-Befehl niemals `-v` hinzu. Wenn der Containername abweicht oder Sie nicht sicher sind, welcher Container alt und welcher neu ist, führen Sie diese Befehle nicht aus; inspizieren Sie den aktuellen Zustand oder bitten Sie einen Administrator um Hilfe. Inspizieren Sie nach dem Rollback die Logs und prüfen Sie, dass Weboberfläche und Daten verfügbar sind.

---

## 95. Persistente Daten nach Upgrade

Der Container-Austausch darf das persistente Docker-Volume nicht entfernen.

Prüfen Sie:

```bash id="j4p8sx"
sudo docker inspect lums \
    --format '{{json .Mounts}}'
```

Bestätigen Sie, dass:

```text id="m7z3kc"
/var/lib/lums
```

vom erwarteten persistenten Volume gestützt wird.

Prüfen Sie dann:

* Benutzer existieren weiterhin
* Rollen sind weiterhin korrekt
* Clients sind weiterhin registriert
* Job-Verlauf bleibt verfügbar
* Audit-Informationen bleiben verfügbar
* Migrationen wurden erfolgreich abgeschlossen

---

## 96. Sicherheitsbasis nach Upgrade

Prüfen Sie nach der Bereitstellung eines neuen Images die gehärtete Laufzeit erneut.

Prüfen Sie:

```bash id="q6c3xv"
sudo docker inspect lums \
    --format '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.Privileged}}'
```

Erwartete Basis:

```text id="s0r8jm"
lums true false
```

Prüfen Sie außerdem:

```text id="g4m2vx"
CapDrop = ALL
SecurityOpt = no-new-privileges:true
```

und dass:

```text id="c3p9rw"
127.0.0.1:5050 → container:5000
```

die Anwendungsexposition bleibt.

Ein erfolgreiches Anwendungsupgrade darf die Sicherheitsbasis nicht stillschweigend schwächen.

---

## 97. Client-Kommunikation nach Upgrade

Prüfen Sie nach einem Server-Upgrade, dass verwaltete Clients weiterhin kommunizieren können.

Prüfen Sie zuerst mindestens einen repräsentativen Client.

Prüfen Sie:

```text id="x8h5qk"
[ ] Client authentication succeeds
[ ] Client report is accepted
[ ] Installed software is available
[ ] Available updates are available
[ ] Update jobs can be created
[ ] Agent results are accepted
```

Wenn mehrere Client-Plattformen bereitgestellt werden, prüfen Sie repräsentative Systeme jeder unterstützten Plattform.

---

## 98. Update-Ausführung nach Upgrade

Führen Sie nach dem Ersetzen des LUMS-Servers nicht sofort ein großes Produktionsupdate durch.

Führen Sie zuerst einen kontrollierten Funktionstest durch.

Ein geeigneter Test sollte den vollständigen Pfad verifizieren:

```text id="y7k2fd"
Web UI
  ↓
API
  ↓
Update Job
  ↓
Agent
  ↓
Package Manager
  ↓
Result
  ↓
Database
  ↓
Web UI
```

Erst nachdem der kontrollierte Test erfolgreich war, sollten normale Wartungsoperationen wieder aufgenommen werden.

---

## 99. Rollback

Ein Rollback sollte möglich sein, wenn ein neues Image ein unerwartetes Produktionsproblem verursacht.

Bewahren Sie:

* vorheriges funktionierendes Image
* persistente Daten
* Datenbank-Backup
* vorherige Konfiguration
* vorheriges TLS-Material
* relevante Logs

Wenn der neue Container nicht nutzbar ist:

1. den neuen Container stoppen
2. ihn zur Untersuchung aufbewahren, wo praktikabel
3. weitere administrative Änderungen stoppen
4. das zuvor als funktionierend bekannte Image wiederherstellen
5. das bestehende persistente Volume weiterverwenden
6. die gehärtete Laufzeit starten
7. die Anwendung prüfen
8. die Clients prüfen
9. den Job-Zustand prüfen
10. das fehlgeschlagene Image separat untersuchen

Entfernen Sie das persistente Volume nicht als Teil eines normalen Rollbacks.

---

## 100. Rollback-Validierung

Prüfen Sie nach dem Rollback:

```text id="z1j8md"
[ ] LUMS starts
[ ] HTTPS works
[ ] Users can authenticate
[ ] Roles are correct
[ ] Clients are present
[ ] Client authentication works
[ ] Job history is available
[ ] Audit information is available
[ ] Package inventory is available
[ ] Update jobs can be tracked
[ ] Security baseline is intact
```

Ein Rollback ist erst abgeschlossen, nachdem die Anwendung und der Client-Kommunikationspfad verifiziert wurden.

---

## 101. Notfall-Administration

Notfall-Administration sollte Beweise und persistenten Zustand bewahren, wo immer möglich.

Beispiele sind:

* wiederholte Anwendungsabstürze
* Datenbank-Integritätsfehler
* weitverbreitete Client-Authentifizierungsfehler
* unerwartetes Paket-Job-Verhalten
* vermutete Offenlegung von Anmeldeinformationen
* defekte Upgrades
* TLS-Fehler, die alle Benutzer betreffen

Die bevorzugte Sequenz ist:

```text id="f8k3wz"
Preserve
   ↓
Observe
   ↓
Isolate
   ↓
Recover
   ↓
Verify
   ↓
Document
```

Vermeiden Sie es, Logs, Datenbanken, Container oder Client-Datensätze nur deshalb zu löschen, weil sie Teil des Problems zu sein scheinen.

---

## 102. Administratives Änderungsprinzip

Jede signifikante Produktionsänderung sollte drei klar definierte Zustände haben:

### Vorher

Der aktuelle Produktionszustand ist bekannt und wiederherstellbar.

### Während

Die Änderung wird mit dem dokumentierten Verfahren durchgeführt.

### Nachher

Der resultierende Zustand wird gegen die erwartete Basis verifiziert.

Dies macht administrative Arbeit reproduzierbar und reduziert versehentliche Konfigurationsdrift.

---

## 103. Kontrollierte Deinstallation

Die Deinstallation ist eine destruktive administrative Operation.

Sie sollte nur durchgeführt werden, wenn die LUMS-Bereitstellung absichtlich entfernt wird.

Bevor Sie LUMS entfernen:

```text id="u5r2nc"
[ ] All managed clients identified
[ ] Active update jobs reviewed
[ ] Required job history exported or preserved
[ ] Required audit information preserved
[ ] Database backup created
[ ] Backup verified
[ ] TLS material preserved if required
[ ] Application secret preserved if required
[ ] Documentation preserved
[ ] Reinstallation requirements documented
```

Entfernen Sie keine persistenten Daten, bevor Sie bestätigt haben, dass sie nicht mehr benötigt werden.

---

## 104. Den Container entfernen

Um den Anwendungscontainer zu entfernen, nachdem die Bereitstellung außer Betrieb genommen wurde:

```bash id="n2x7kc"
sudo docker stop lums
sudo docker rm lums
```

Das Docker-Volume wird durch diese Befehle absichtlich **nicht** entfernt.

Dies ermöglicht, dass die Anwendungsdaten für spätere Inspektion oder Wiederherstellung verfügbar bleiben.

---

## 105. Persistente Daten entfernen

Das Entfernen des LUMS-Docker-Volumes ist eine separate destruktive Operation.

Führen Sie dies erst durch, nachdem Sie bestätigt haben, dass die Datenbank und der gesamte gespeicherte Anwendungszustand nicht mehr benötigt werden.

Beispiel:

```bash id="r8w3mz"
sudo docker volume rm lums-data
```

Dies entfernt dauerhaft die persistenten Anwendungsdaten, die in diesem Volume gespeichert sind.

Führen Sie diesen Befehl nicht während eines normalen Upgrades oder Rollbacks aus.

---

## 106. Client-Komponenten entfernen

Wenn ein verwalteter Client dauerhaft aus LUMS entfernt wird, deinstallieren oder deaktivieren Sie seine Agent-Komponenten gemäß dem Betriebssystemverfahren des Clients.

Der Client sollte nach der Außerbetriebnahme nicht mehr an den LUMS-Server berichten.

Bewahren Sie relevante Job- und Audit-Informationen vor dem Entfernen des Clients auf, wenn historische Aufzeichnungen erforderlich sind.

---

## 107. Abschließende administrative Checkliste

### Benutzeradministration

```text id="p5z8cv"
[ ] Users have appropriate roles
[ ] Administrator access is limited
[ ] Disabled accounts are reviewed
[ ] Credentials are protected
```

### Client-Administration

```text id="q2m7xd"
[ ] Clients are correctly registered
[ ] Client tokens are protected
[ ] Disabled clients are reviewed
[ ] Token rotation is performed when required
[ ] Client reporting is healthy
```

### Update-Administration

```text id="h6v9kt"
[ ] Available updates are reviewed
[ ] Update jobs are monitored
[ ] Failed jobs are investigated
[ ] Package operations are verified
[ ] Reboot requirements are checked
[ ] Job history is retained
```

### Server-Administration

```text id="r3c8wn"
[ ] Container is running
[ ] Persistent volume is attached
[ ] SQLite integrity is healthy
[ ] HTTPS is working
[ ] TLS material is valid
[ ] Application secret is protected
[ ] Backups are available
```

### Sicherheit

```text id="v7m4qx"
[ ] RBAC remains enforced
[ ] Viewer restrictions remain intact
[ ] Client authentication works
[ ] Container remains hardened
[ ] Application port remains localhost-only
[ ] No credentials are exposed
[ ] Logs contain no unexplained sensitive information
```

---

## 108. Operative Basis

Eine gesunde LUMS-Installation sollte die folgende Basis erfüllen:

```text id="d4k9sy"
Application
    ├── HTTPS available
    ├── Authentication available
    └── RBAC enforced

Server
    ├── Hardened container
    ├── Persistent database
    └── Valid migrations

Clients
    ├── Authenticated
    ├── Reporting
    ├── Software inventory available
    └── Update information available

Operations
    ├── Update jobs executable
    ├── Results recorded
    ├── Recovery supported
    └── Reboot state reported

Security
    ├── Secrets protected
    ├── Tokens protected
    ├── Audit information retained
    └── Network exposure restricted

Recovery
    ├── Backups available
    ├── Restore path known
    └── Rollback path known
```

---

## 109. Administration abgeschlossen

Die LUMS-Administration sollte immer kontrollierte, beobachtbare und umkehrbare Änderungen priorisieren.

Der administrative Lebenszyklus ist:

```text id="w6f1pa"
Plan
  ↓
Observe
  ↓
Change
  ↓
Verify
  ↓
Document
  ↓
Maintain
```

Die wichtigsten operativen Prinzipien sind:

> **Verwenden Sie das geringstmögliche Privileg.**

> **Bewahren Sie persistente Daten.**

> **Ändern Sie keinen Zustand, ohne den aktuellen Zustand zu verstehen.**

> **Verifizieren Sie das Ergebnis jeder signifikanten Operation.**

> **Halten Sie einen getesteten Wiederherstellungspfad bereit.**

Für Installationsverfahren siehe `install.md`.

Für Sicherheitsarchitektur und Audit-Ergebnisse siehe `security.md`.

Für Diagnose- und Wiederherstellungsverfahren siehe `troubleshooting.md`.

---

## 110. Abschließendes Administrationsprinzip

LUMS soll Linux-Update-Management vorhersehbar und beobachtbar machen.

Administrative Arbeit sollte daher nicht auf Annahmen oder blindem Wiederholen basieren.

Wenn sich etwas ändert:

**Zuerst beobachten. Zweitens ändern. Drittens verifizieren.**

Wenn etwas kaputtgeht:

**Beweise sichern. Die Fehlerschicht identifizieren. Bewusst wiederherstellen.**

Wenn etwas funktioniert:

**Das Ergebnis aufzeichnen und die als funktionierend bekannte Basis beibehalten.**
