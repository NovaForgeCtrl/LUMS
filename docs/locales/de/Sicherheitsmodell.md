# LUMS Sicherheitsdokumentation

**LUMS — Linux Update Management Server**

Dieses Dokument beschreibt die aktuelle Sicherheitsarchitektur, implementierte Sicherheitskontrollen, Ergebnisse des Sicherheitsaudits, operative Einschränkungen und sicherheitsrelevante Designentscheidungen von LUMS.

Das Dokument spiegelt den **aktuell implementierten Systemzustand** wider. Geplante oder zukünftige Verbesserungen sind ausdrücklich als solche gekennzeichnet.

---

# Sicherheitsprinzipien

LUMS folgt einem Defense-in-Depth-Ansatz für Linux-Update-Management.

Das Sicherheitsmodell trennt administrative Authentifizierung, Client-Authentifizierung, Autorisierung, kontrollierte Update-Ausführung und Audit-Logging.

Die primären Sicherheitsziele sind:

* authentifizierter administrativer Zugriff
* rollenbasierte Autorisierung
* authentifizierte Client-Kommunikation
* kontrollierte Update-Ausführung
* Schutz vor gleichzeitiger Job-Ausführung
* wiederherstellbare Update-Jobs
* geschützte Secrets
* kontrollierte Container-Ausführung
* auditierbare sicherheitssensible Operationen
* vorhersehbare Fehlerbehandlung
* Sicherheitsregressionstests

LUMS ist primär für kontrollierte Infrastruktur-, Labor- und interne Netzwerkumgebungen vorgesehen.

Es sollte nicht ohne eine zusätzliche Sicherheitsüberprüfung und angemessene Netzwerkkontrollen direkt dem öffentlichen Internet ausgesetzt werden.

---

# Sicherheitsarchitektur

LUMS besteht aus den folgenden sicherheitsrelevanten Komponenten:

* Web-Administrationsoberfläche
* REST-API
* SQLite-Datenbank
* LUMS Agent auf verwalteten Clients
* APT- und pacman-Paketverwaltungs-Backends
* Update-Job- und Wiederherstellungsmechanismen
* Nginx-HTTPS-Reverse-Proxy
* Gehärteter Docker-Container

Der grundlegende Management-Fluss ist:

Browser → HTTPS/Nginx → LUMS API → SQLite → LUMS Agent → Paketmanager → Ergebnis → SQLite → Web-UI

Authentifizierung und Autorisierung sind absichtlich getrennt.

Eine gültige authentifizierte Sitzung gewährt nicht automatisch Zugriff auf jede administrative Operation.

Die Autorisierung wird serverseitig durchgesetzt. Die Weboberfläche blendet zusätzlich Funktionen aus, die für die aktuelle Rolle nicht verfügbar sind, aber die UI-Sichtbarkeit wird niemals als Sicherheitsgrenze behandelt.

---

## Administrative Authentifizierung

Administrative Benutzer authentifizieren sich über die LUMS-Weboberfläche.

Passwörter werden niemals im Klartext gespeichert. LUMS verwendet Argon2-basiertes Passwort-Hashing für die Passwortspeicherung.

Administrative Sitzungen verwenden:

* authentifizierte serverseitige Sitzungsverwaltung
* Sitzungsablauf
* Sitzungsregeneration
* CSRF-Schutz für zustandsändernde Browser-Anfragen
* Login-Ratenbegrenzung
* Sitzungsinvalidierung während der Abmeldung
* serverseitige Rollenvalidierung

Authentifizierung und Autorisierung bleiben getrennte Sicherheitskontrollen.

Ein erfolgreich authentifizierter Benutzer muss dennoch die erforderliche Berechtigung für geschützte Operationen besitzen.

---

# Rollenbasierte Zugriffskontrolle

LUMS unterstützt derzeit drei Web-Benutzerrollen:

* `administrator`
* `operator`
* `viewer`

Rollenvorlagen werden in `users.role` gespeichert; individuelle Berechtigungen werden serverseitig in `user_permissions` gespeichert.

Der Server lädt die effektiven Berechtigungen für jedes authentifizierte Konto. Clientseitige Berechtigungsinformationen steuern nur die Darstellung und ersetzen niemals die serverseitige Autorisierung.

## Administrator

Administratoren haben vollständigen administrativen und operativen Zugriff.

Sie können:

* Clients anzeigen
* Clients erstellen
* Clients deaktivieren
* Client-Tokens rotieren
* installierte Pakete und verfügbare Updates anzeigen
* Update-Jobs erstellen
* unterstützte Update-Operationen ausführen
* Update-Job-Verlauf anzeigen
* Paketverwaltung verwenden
* Systemwartungsfunktionen verwenden
* Benutzer verwalten
* Benutzerrollen verwalten
* auf administrative Funktionen zugreifen

## Operator

Operatoren können operative Update-Management-Aufgaben durchführen.

Sie können:

* Clients anzeigen
* installierte Pakete und verfügbare Updates anzeigen
* Update-Jobs erstellen
* unterstützte Update-Operationen ausführen
* Update-Job-Verlauf anzeigen
* Paketverwaltung verwenden
* Systemwartungsfunktionen verwenden

Operatoren können nicht:

* Benutzer verwalten
* Benutzerrollen ändern
* Clients erstellen
* Clients deaktivieren
* Client-Tokens rotieren

## Viewer

Viewer haben eingeschränkten schreibgeschützten Zugriff.

Sie können:

* Clients anzeigen
* installierte Software anzeigen

Die folgenden Managementbereiche sind für Viewer-Konten ausgeblendet:

* Updates
* Update-Jobs
* Update-Verlauf
* Paketverwaltung
* Systemwartung

Viewer-Konten können keine zustandsändernden Update-Management-Operationen durchführen.

Der Server setzt diese Einschränkungen unabhängig durch Authentifizierung und benutzerspezifische Berechtigungsprüfungen durch.

---

# Client-Authentifizierung

Jeder verwaltete LUMS-Client verwendet einen individuellen Bearer-Token.

Der Authentifizierungsmechanismus folgt dem Modell:

`Authorization: Bearer <CLIENT_TOKEN>`

Der Server speichert Client-Tokens nicht als Klartextwerte.

Stattdessen speichert LUMS einen SHA-256-Hexadezimal-Digest des Client-Tokens.

Der Authentifizierungsablauf ist:

Client-Token → SHA-256 → Token-Digest → SQLite

Die Client-Authentifizierung verifiziert den authentifizierten Token gegen den registrierten Client und prüft zusätzlich den relevanten Client-Zustand.

Das Sicherheitsmodell verwendet keine Quell-IP-Adresse als alleinigen Beweis der Client-Identität.

Dies ermöglicht LUMS den Betrieb in:

* privaten Labornetzwerken
* isolierter Infrastruktur
* NAT-basierten Netzwerken
* Offline-Umgebungen
* Netzwerken, in denen sich Client-Adressen ändern können

Client-Tokens können von autorisierten Administratoren rotiert werden.

Eine Token-Rotation generiert einen Ersatz-Token, speichert nur dessen Digest, invalidiert den vorherigen Token, zeichnet die administrative Aktion im Audit-Log auf und präsentiert den Ersatz-Token einmalig.

Klartext-Client-Token-Werte werden nicht in Audit-Datensätzen geschrieben.

---

# Sicherheitsaudit

Das Sicherheitsaudit wird inkrementell durchgeführt.

Jeder Auditbereich wird gegen die tatsächliche Implementierung überprüft, gefolgt von automatisierten Tests, isolierter Verifikation oder Produktionsverifikation, wo anwendbar.

Aktuelle Auditbereiche:

| Audit | Bereich                                | Status                    |
| ----- | -------------------------------------- | ------------------------- |
| #01   | SQLite-Fremdschlüssel                  | BESTANDEN                 |
| #02   | SQLite-Laufzeitkonfiguration           | BESTANDEN                 |
| #03   | Update-Timeout-Behandlung              | BESTANDEN                 |
| #04   | Login-Ratenbegrenzung                  | BESTANDEN                 |
| #05   | API-Eingabevalidierung                 | BESTANDEN                 |
| #06   | Sitzungswiderruf                       | BESTANDEN                 |
| #07   | Client-Token-Rotation                  | BESTANDEN                 |
| #08   | IP-Adressbehandlung / Offline-Netzwerke | BESTANDEN                |
| #09   | Job-Wiederherstellung / Checkpointing  | BESTANDEN                 |
| #10   | APT-Robustheit                         | BESTANDEN                 |
| #11   | Arch-Reboot-Erkennung                  | BESTANDEN                 |
| #12   | Unit-Tests / API-Ergebnisvalidierung   | BESTANDEN                 |
| #13   | Simulationstests                       | BESTANDEN                 |
| #14   | Kontinuierliche Integration            | BESTANDEN                 |
| #15   | Anwendungs-/Audit-Logging              | BESTANDEN                 |
| #16   | Versionierung / Releases               | ÜBERPRÜFT — DESIGNBEDINGT OFFEN |
| #17   | Rollenbasierte Zugriffskontrolle       | BESTANDEN                 |
| #18   | Dokumentationsüberprüfung              | IN BEARBEITUNG            |

Audit #16 unterscheidet sich absichtlich von den technischen Sicherheitskontrollen oben.

LUMS hat derzeit kein offizielles stabiles Release, keinen Release-Tag und kein GitHub-Release. Dies ist beabsichtigt, weil das Projekt sich weiterhin in aktiver Entwicklung befindet.

Audit #18 bleibt offen, bis das vollständige Dokumentationsset überprüft und mit der aktuellen Implementierung synchronisiert wurde.

# Sicherheitsaudit #01

## SQLite-Fremdschlüssel

Die SQLite-Fremdschlüssel-Durchsetzung ist für Anwendungsdatenbankverbindungen aktiviert.

Die Anwendung aktiviert ausdrücklich:

`PRAGMA foreign_keys = ON`

Dies stellt sicher, dass referenzielle Integrität für Beziehungen zwischen verwandten Datenbankdatensätzen durchgesetzt wird.

Das Audit verifizierte:

* Laufzeit-Fremdschlüssel-Durchsetzung
* Fremdschlüssel-Integrität
* Client-Lebenszyklusverhalten
* Client-Deaktivierungsverhalten
* Erhaltung historischer Job-Informationen
* Erhaltung von Audit-Informationen

Der Client-Zustand wird konservativ behandelt.

Wo angebracht, werden Clients deaktiviert, anstatt sie auf eine Weise zu entfernen, die historische operative Informationen zerstören würde.

**Status: BESTANDEN**

---

# Sicherheitsaudit #02

## SQLite-Laufzeitkonfiguration

Die SQLite-Produktionsdatenbank wurde auf ihre Laufzeitkonfiguration überprüft.

Die verifizierte Produktionskonfiguration ist:

* `journal_mode`: `wal`
* `busy_timeout`: `5000`
* `synchronous`: `2`

Die Anwendung aktiviert ausdrücklich:

`PRAGMA foreign_keys = ON`

Die Produktionsdatenbank verwendet derzeit WAL-Modus.

Die Datenbankkonfiguration wurde basierend auf dem tatsächlich verifizierten Produktionszustand dokumentiert, nicht auf der historischen Entwicklungskonfiguration.

Der konfigurierte Busy-Timeout reduziert sofortige Datenbankfehler, wenn eine andere Transaktion die Datenbank vorübergehend hält.

Die Fremdschlüssel-Einstellung auf Anwendungsebene stellt referenzielle Integrität für jede Datenbankverbindung sicher.

Das Audit umfasste die Produktionsverifikation der aktiven SQLite-Konfiguration.

**Status: BESTANDEN**

---

# Sicherheitsaudit #03

## Update-Timeout und Prozessbehandlung

Die Update-Ausführung ist gegen unbegrenzt blockierende Paketmanager-Prozesse geschützt.

Der Ausführungsfluss ist:

Prozess starten
↓
Prozessausgabe lesen
↓
Timeout überwachen
↓
Timeout erreicht?
↓
Prozess beenden
↓
Karenzzeit
↓
Prozess läuft noch?
↓
Prozess töten, falls erforderlich
↓
Job abschließen

Die Implementierung verwendet kontrollierte Subprozess-Behandlung, sodass stille Prozesse nicht unbegrenzt blockieren können, während sie auf Ausgabe warten.

Die Timeout-Behandlung wurde getestet gegen:

* stille Prozesse
* normale Prozessbeendigung
* Timeout-Bedingungen
* Prozesse, die normaler Beendigung widerstehen
* Kill-Fallback
* Timeout-Verhalten auf Integrationsebene

Der Timeout-Mechanismus verhindert, dass eine paketverwaltungsbezogene Operation unbegrenzt in einem aktiven Zustand verbleibt.

Fehler und Timeout-Bedingungen werden als kontrollierte Job-Ergebnisse zurückgegeben und im Job-Zustand aufgezeichnet.

Die aktuell dokumentierte LUMS Agent-Version ist:

`1.7.0`

**Status: BESTANDEN**

---

# Sicherheitsaudit #04

## Login-Ratenbegrenzung

Administrative Login-Versuche sind ratenbegrenzt.

Die aktuelle Eskalationsrichtlinie ist:

* 5 fehlgeschlagene Versuche → 30 Sekunden
* 6 fehlgeschlagene Versuche → 60 Sekunden
* 7 fehlgeschlagene Versuche → 120 Sekunden
* 8 oder mehr fehlgeschlagene Versuche → 300 Sekunden

Der Rate-Limit-Zustand wird in SQLite persistiert.

Gleichzeitige Login-Fehler verwenden transaktionales Datenbank-Sperren mit:

`BEGIN IMMEDIATE`

Dies verhindert, dass gleichzeitige Authentifizierungsfehler den beabsichtigten Rate-Limit-Zustand durch Race-Conditions umgehen können.

Eine erfolgreiche Authentifizierung löscht den zutreffenden Fehlerzustand.

Das Audit umfasste:

* isoliertes Rate-Limit-Verhalten
* gleichzeitige Authentifizierungsfehler
* Transaktions-Rollback
* Datenbank-Lock-Behandlung
* Reset-Verhalten bei erfolgreichem Login
* Rate-Limit-Audit-Ereignisse
* Produktions-Login-Verhalten

Der Rate-Limiter bietet daher eine serverseitige Kontrolle gegen wiederholte Authentifizierungsversuche, anstatt sich auf clientseitiges Verhalten zu verlassen.

**Status: BESTANDEN**

---

# Auditstatus nach Teil 2

Die ersten vier Sicherheitsauditbereiche sind abgeschlossen:

| Audit | Bereich                              | Status   |
| ----- | ------------------------------------ | -------- |
| #01   | SQLite-Fremdschlüssel                | BESTANDEN |
| #02   | SQLite-Laufzeitkonfiguration         | BESTANDEN |
| #03   | Update-Timeout / Prozessbehandlung   | BESTANDEN |
| #04   | Login-Ratenbegrenzung                | BESTANDEN |

Die folgenden Auditbereiche sind in den nachfolgenden Abschnitten dokumentiert:

* #05 API-Eingabevalidierung
* #06 Sitzungswiderruf
* #07 Client-Token-Rotation
* #08 IP-Adressbehandlung / Offline-Netzwerke
* #09 Job-Wiederherstellung / Checkpointing
* #10 APT-Robustheit
* #11 Arch-Reboot-Erkennung
* #12 Unit-Tests / API-Ergebnisvalidierung
* #13 Simulationstests
* #14 Kontinuierliche Integration
* #15 Anwendungs-/Audit-Logging
* #16 Versionierung / Releases
* #17 Rollenbasierte Zugriffskontrolle

Audit #18 — Dokumentationsüberprüfung — bleibt offen, bis das vollständige Dokumentationsset überprüft und mit der aktuellen Implementierung synchronisiert wurde.

# Sicherheitsaudit #05

## API-Eingabevalidierung

LUMS validiert sicherheitssensible API-Eingaben auf der Serverseite.

Vom Client bereitgestellte Werte werden nicht allein deshalb vertraut, weil sie von der authentifizierten Weboberfläche oder einem registrierten Client stammen.

Die Validierung wird auf relevante API-Parameter angewendet, einschließlich:

* Client-Identifikatoren
* Paketnamen
* Update-Job-Aktionen
* Paketlisten
* Suchparameter
* Benutzerverwaltungsparameter
* Client-Token-Operationen
* Job-Ergebnisdaten

Paketnamen werden validiert, bevor sie an paketverwaltungsbezogene Operationen übergeben werden.

Die Update-Job-API akzeptiert nur ausdrücklich unterstützte Aktionen.

Die derzeit unterstützten paketbezogenen Aktionen sind:

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

Unerwartete Aktionen werden abgelehnt.

Paketlisten werden vor der Job-Erstellung validiert.

Für `UPDATE_PACKAGE` muss das angeforderte Paket außerdem in den verfügbaren Update-Informationen des Clients vorhanden sein.

Datenbankabfragen verwenden parametrisiertes SQL, anstatt SQL-Anweisungen aus nicht vertrauenswürdiger Eingabe zu konstruieren.

Dies verhindert, dass benutzergesteuerte Werte als SQL-Syntax interpretiert werden.

Das Audit umfasste Negativ-Eingabetests und SQL-Injection-orientierte Testfälle.

Die Validierungskontrollen wurden auch durch die automatisierte Testsuite verifiziert.

**Status: BESTANDEN**

---

# Sicherheitsaudit #06

## Sitzungswiderruf

LUMS schützt authentifizierte administrative Sitzungen gegen weitere Nutzung nach der Abmeldung.

Die Sitzungsverwaltung umfasst:

* authentifizierte serverseitige Sitzungen
* Sitzungsablauf
* Sitzungsregeneration
* Logout-Invalidierung
* serverseitige Authentifizierungsprüfungen
* serverseitige Rollenvalidierung

Die Abmeldung invalidiert die aktive authentifizierte Sitzung.

Geschützte API-Endpunkte erfordern eine authentifizierte Sitzung und verlassen sich nicht auf clientseitigen Zustand, um festzustellen, ob der Benutzer weiterhin authentifiziert ist.

Der Sitzungszustand wird daher vom Server für geschützte Operationen ausgewertet.

Zustandsändernde Browser-Anfragen erfordern zusätzlich CSRF-Schutz.

Das Audit verifizierte, dass:

* authentifizierter Zugriff normal funktioniert
* geschützte Endpunkte nicht authentifizierte Anfragen ablehnen
* die Abmeldung die aktive Sitzung invalidiert
* eine zuvor authentifizierte Sitzung nach dem Widerruf nicht weiterhin geschützte Funktionalität verwenden kann
* Rolleninformationen serverseitig ausgewertet werden

**Status: BESTANDEN**

---

# Sicherheitsaudit #07

## Client-Token-Rotation

Jeder verwaltete LUMS-Client verwendet einen individuellen Authentifizierungstoken.

Client-Tokens werden nicht als Klartextwerte gespeichert.

Stattdessen speichert LUMS den SHA-256-Hexadezimal-Digest des Client-Tokens.

Das Authentifizierungsmodell ist:

`Authorization: Bearer <CLIENT_TOKEN>`

Der Server hasht den übergebenen Token und vergleicht den resultierenden Digest mit dem registrierten Client-Token-Digest.

Autorisierte Administratoren können den Token eines Clients rotieren.

Die Token-Rotation führt die folgenden Operationen durch:

1. Einen Ersatz-Token generieren.
2. Dessen SHA-256-Digest berechnen.
3. Den gespeicherten Client-Token-Digest ersetzen.
4. Den vorherigen Token invalidieren.
5. Die administrative Aktion im Audit-Log aufzeichnen.
6. Den Ersatz-Token dem Administrator präsentieren.

Der vorherige Token kann sich nach der Rotation nicht mehr authentifizieren.

Klartext-Token-Werte werden nicht in Audit-Logs geschrieben.

Das Audit verifizierte:

* erfolgreiche Token-Authentifizierung
* Token-Digest-Speicherung
* Token-Rotation
* Invalidierung des vorherigen Tokens
* Authentifizierung mit dem Ersatz-Token
* Autorisierungsanforderungen für die Token-Rotation
* Audit-Logging
* Schutz gegen nicht autorisierte Rotation

Die Client-Token-Rotation ist auf Administratoren beschränkt.

Operatoren und Viewer können Client-Tokens nicht rotieren.

**Status: BESTANDEN**

---

# Sicherheitsaudit #08

## IP-Adressbehandlung und Offline-Netzwerke

LUMS verwendet die Quell-IP-Adresse eines Clients nicht als alleinigen Beweis der Client-Identität.

Die Client-Authentifizierung basiert auf dem registrierten Client-Token.

Dieses Design ist beabsichtigt, weil verwaltete Clients in Umgebungen betrieben werden können, in denen sich ihre Netzwerkadresse ändert.

Unterstützte Bereitstellungsszenarien umfassen:

* private Labornetzwerke
* NAT-basierte Netzwerke
* isolierte Infrastruktur
* dynamisch adressierte Clients
* Offline-Umgebungen
* kontrollierte interne Netzwerke

Der Server trennt daher:

**Netzwerkstandort**

von:

**Client-Identität**

Ein gültiger Client-Token identifiziert den registrierten Client.

Die Netzwerkadresse des Clients kann weiterhin für operative und Audit-Zwecke aufgezeichnet werden, wird aber nicht als Authentifizierungs-Credential behandelt.

Die Implementierung vermeidet außerdem Annahmen, dass ein Client von einer festen Adresse aus erreichbar sein muss.

Dies ist besonders wichtig für Laborumgebungen und Infrastruktur, in denen sich die Netzwerktopologie ändern kann, ohne die logische Identität des verwalteten Systems zu ändern.

Das Audit verifizierte die Client-Authentifizierung ohne Abhängigkeit von einer festen Quell-IP-Adresse.

**Status: BESTANDEN**

---

# Auditstatus nach Teil 3

Die folgenden Sicherheitsauditbereiche sind abgeschlossen:

| Audit | Bereich                                | Status   |
| ----- | -------------------------------------- | -------- |
| #01   | SQLite-Fremdschlüssel                  | BESTANDEN |
| #02   | SQLite-Laufzeitkonfiguration           | BESTANDEN |
| #03   | Update-Timeout / Prozessbehandlung     | BESTANDEN |
| #04   | Login-Ratenbegrenzung                  | BESTANDEN |
| #05   | API-Eingabevalidierung                 | BESTANDEN |
| #06   | Sitzungswiderruf                       | BESTANDEN |
| #07   | Client-Token-Rotation                  | BESTANDEN |
| #08   | IP-Adressbehandlung / Offline-Netzwerke | BESTANDEN |

Der nächste Abschnitt behandelt:

* #09 Job-Wiederherstellung / Checkpointing
* #10 APT-Robustheit
* #11 Arch-Reboot-Erkennung
* #12 Unit-Tests / API-Ergebnisvalidierung

# Sicherheitsaudit #09

## Job-Wiederherstellung und Checkpointing

LUMS-Update-Jobs sind darauf ausgelegt, sich sicher von unterbrochener Ausführung zu erholen.

Update-Jobs pflegen persistenten Zustand in der SQLite-Datenbank.

Einzelne Paketoperationen werden getrennt vom Gesamtjobzustand verfolgt.

Dies ermöglicht es dem Agent festzustellen, welche Paketoperationen bereits erfolgreich abgeschlossen wurden, bevor ein unterbrochener Job fortgesetzt wird.

Während der Wiederherstellung werden erfolgreich abgeschlossene Paketoperationen nicht erneut ausgeführt.

Die Wiederherstellungslogik folgt daher dem Prinzip:

`Persistent Job State → Determine Completed Work → Skip Completed Items → Continue Remaining Work`

Dies reduziert das Risiko unnötiger wiederholter Paketoperationen nach:

* Agent-Unterbrechung
* Prozessbeendigung
* Systemneustart
* vorübergehendem Kommunikationsfehler
* Container-Neustart
* anderen Ausführungsunterbrechungen

Das Audit verifizierte das Wiederherstellungs- und Checkpoint-Verhalten unterbrochener Jobs.

Die Wiederherstellung wurde mit Jobs getestet, die mehrere Paketoperationen enthielten, sowie mit zuvor erfolgreichen Paket-Elementen.

Das Audit bestätigte, dass abgeschlossene Arbeit bewahrt wird und verbleibende Arbeit fortgesetzt werden kann, ohne erfolgreiche Operationen unnötig zu wiederholen.

**Status: BESTANDEN**

---

# Sicherheitsaudit #10

## APT-Robustheit

Debian-basierte Paketoperationen werden über die LUMS-Paketverwaltungsschicht ausgeführt.

APT-bezogene Update-Operationen wurden auf zuverlässige Erkennung des Paketmanager-Zustands und der Update-Ergebnisse überprüft.

Die Implementierung berücksichtigt Fälle, in denen paketverwaltungsbezogene Befehle erfolgreich zurückkehren können, während eine zusätzliche Interpretation ihrer Ausgabe oder des resultierenden Systemzustands erforderlich ist.

Die APT-Update-Erkennung wurde gehärtet, um sich nicht auf eine einzelne vereinfachte Befehlsausgabe-Bedingung zu verlassen.

Das Audit umfasste Tests von:

* normalen APT-Operationen
* verfügbaren Paket-Updates
* Paketinstallation
* Paketentfernung
* Update-Job-Ausführung
* APT-Ergebnisbehandlung
* Update-Erkennungsverhalten

Die entsprechende Härtung wurde committet als:

`c76f331 security: harden apt update detection`

Das Ziel ist sicherzustellen, dass LUMS den Paketverwaltungszustand nicht fälschlicherweise allein basierend auf unvollständiger oder mehrdeutiger Befehlsausgabe meldet.

**Status: BESTANDEN**

---

# Sicherheitsaudit #11

## Arch Linux Reboot-Erkennung

Arch Linux-Paketoperationen können zu einem Systemzustand führen, in dem ein Reboot erforderlich oder empfohlen ist.

LUMS wertet daher den resultierenden Systemzustand nach relevanten paketverwaltungsbezogenen Operationen aus.

Der Agent unterscheidet den normalen Abschluss einer Paketoperation von Situationen, in denen ein Reboot erforderlich ist.

Der Reboot-Zustand wird als Teil des Job-Ergebnisses an den LUMS-Server zurückgemeldet.

Dies ermöglicht es der Management-Oberfläche, zu unterscheiden zwischen:

* erfolgreicher Paketoperation
* erfolgreicher Operation mit Reboot-Anforderung
* fehlgeschlagener Operation

Das Audit verifizierte die Arch Linux-Reboot-Erkennung unter Verwendung des tatsächlichen paketverwaltungsbezogenen Ausführungspfads.

Die Implementierung wurde gegen Reboot-Required-Bedingungen und normale Abschlussbedingungen getestet.

**Status: BESTANDEN**

---

# Sicherheitsaudit #12

## Unit-Tests und API-Ergebnisvalidierung

Sicherheitssensibles Verhalten ist durch automatisierte Tests abgedeckt.

Die Testsuite umfasst Abdeckung für Authentifizierung, Autorisierung, API-Validierung, Update-Jobs, Paketverwaltung, Client-Authentifizierung und Ergebnisbehandlung.

Der Agent-zu-Server-Ergebnispfad wurde speziell überprüft, um sicherzustellen, dass Job-Ergebnisse nicht willkürlich unzusammenhängenden serverseitigen Zustand verändern können.

Die Ergebnisverarbeitung validiert die übermittelten Informationen, bevor Zustandsänderungen auf den entsprechenden Update-Job angewendet werden.

Die Validierung umfasst relevante Ergebnisfelder und erwartete Job-Beziehungen.

Dies verhindert, dass ein authentifizierter Client frei unzusammenhängende Jobs auswählen oder willkürlichen Zustand in die Update-Job-Datenbank injizieren kann.

Die Sicherheitstestsuite umfasst auch Negativ- und nicht autorisierte Fälle.

Führen Sie die vollständige automatisierte Testsuite vom Repository-Stamm aus mit
`./.venv-test/bin/pytest -q` aus. Die Anzahl der Tests ändert sich im Laufe der Zeit; verwenden Sie das Ergebnis des aktuellen Laufs anstelle einer festen Anzahl in diesem Dokument.

Die relevanten Sicherheitskontrollen wurden während des Audits zusätzlich durch fokussierte Testläufe verifiziert.

**Status: BESTANDEN**

---

# Auditstatus nach Teil 4

Die folgenden Sicherheitsauditbereiche sind abgeschlossen:

| Audit | Bereich                                | Status   |
| ----- | -------------------------------------- | -------- |
| #01   | SQLite-Fremdschlüssel                  | BESTANDEN |
| #02   | SQLite-Laufzeitkonfiguration           | BESTANDEN |
| #03   | Update-Timeout / Prozessbehandlung     | BESTANDEN |
| #04   | Login-Ratenbegrenzung                  | BESTANDEN |
| #05   | API-Eingabevalidierung                 | BESTANDEN |
| #06   | Sitzungswiderruf                       | BESTANDEN |
| #07   | Client-Token-Rotation                  | BESTANDEN |
| #08   | IP-Adressbehandlung / Offline-Netzwerke | BESTANDEN |
| #09   | Job-Wiederherstellung / Checkpointing  | BESTANDEN |
| #10   | APT-Robustheit                         | BESTANDEN |
| #11   | Arch-Reboot-Erkennung                  | BESTANDEN |
| #12   | Unit-Tests / API-Ergebnisvalidierung   | BESTANDEN |

Der nächste Abschnitt behandelt:

* #13 Simulationstests
* #14 Kontinuierliche Integration
* #15 Anwendungs-/Audit-Logging
* #16 Versionierung / Releases

# Sicherheitsaudit #13

## Simulationstests

LUMS bietet einen Simulationsmechanismus zum Testen von Update-Management-Workflows, ohne die entsprechende paketverwaltungsbezogene Operation auf dem verwalteten System durchzuführen.

Die Simulation ist auf der Agent-Ausführungsschicht implementiert.

Wenn die Simulation aktiviert ist, werden paketverwaltungsbezogene Operationen dargestellt und verarbeitet, ohne die angeforderte Paketänderung auf das Betriebssystem anzuwenden.

Dies ermöglicht das Testen von Update-Job-Verhalten, ohne das verwaltete System absichtlich zu verändern.

Die Simulationstests decken relevante Update-Management-Pfade ab, einschließlich:

* Paketinstallation
* Paketentfernung
* Paket-Updates
* Systemupdates
* Job-Ausführung
* Ergebnisberichterstattung
* erfolgreicher Abschluss
* Fehlerbehandlung

Der Simulationsmechanismus wurde während des Sicherheitsaudits verwendet, um Job-Erstellung, Agent-Ausführung, Ergebnisbehandlung und serverseitige Zustandsübergänge unabhängig von echten Paketänderungen zu verifizieren.

Der Simulationsmodus ist ein Testmechanismus und ersetzt nicht die Autorisierungskontrollen normaler Update-Operationen.

**Status: BESTANDEN**

---

# Sicherheitsaudit #14

## Kontinuierliche Integration

LUMS verwendet automatisierte Tests, um Sicherheits- und Funktionsregressionen zu erkennen, bevor Änderungen als abgeschlossen gelten.

Der CI-Prozess führt die automatisierte Testsuite gegen das Projekt aus.

Die Testumgebung verifiziert die Anwendung und sicherheitssensible Funktionalität unabhängig vom Produktionscontainer.

Der CI-Prozess umfasst die Validierung von:

* Authentifizierung
* Autorisierung
* RBAC
* API-Verhalten
* Update-Job-Behandlung
* Paketverwaltungsverhalten
* Client-Authentifizierung
* Job-Ergebnisvalidierung
* sicherheitssensible Fehlerbehandlung

Das CI-Audit wurde nach den Sicherheitshärtungsänderungen überprüft.

Die abschließend verifizierte Testsuite wurde erfolgreich abgeschlossen.

Die Testanzahl ändert sich, während sich das Projekt weiterentwickelt. CI bietet eine automatisierte Regressionsbarriere für sicherheitsrelevante Anwendungsänderungen.

**Status: BESTANDEN**

---

# Sicherheitsaudit #15

## Anwendungs- und Audit-Logging

LUMS zeichnet sicherheitssensible administrative und operative Ereignisse durch Audit-Logging auf Anwendungsebene auf.

Das Audit-Logging ist darauf ausgelegt, einen operativen Verlauf bereitzustellen, ohne sensible Anmeldeinformationen zu speichern.

Relevante sicherheitssensible Aktionen umfassen Ereignisse wie:

* authentifizierungsbezogene Sicherheitsereignisse
* administrative Aktionen
* Client-Verwaltung
* Client-Token-Operationen
* Update-Job-Erstellung
* Update-Job-Ausführung
* sicherheitsrelevante Fehler

Sensibles Credential-Material ist von Audit-Datensätzen ausgeschlossen.

Insbesondere:

* Passwörter werden nicht geloggt
* Klartext-Client-Tokens werden nicht geloggt
* Secret-Werte werden nicht absichtlich in Audit-Datensätze geschrieben

Audit-Datensätze werden, wo anwendbar, mit dem relevanten administrativen oder operativen Kontext verknüpft.

Die Audit-Logging-Implementierung wurde überprüft auf:

* Abdeckung sicherheitssensibler Ereignisse
* Credential-Ausschluss
* administrative Nachvollziehbarkeit
* Fehlerbehandlung
* Persistenz relevanter Audit-Informationen

Das Logging-System ist darauf ausgelegt, sowohl operative Fehlerbehebung als auch Sicherheitsuntersuchungen zu unterstützen.

**Status: BESTANDEN**

---

# Sicherheitsaudit #16

## Versionierung und Releases

Versionierung und Release-Management wurden als Teil des Sicherheitsaudits überprüft.

LUMS befindet sich derzeit in aktiver Entwicklung und hat noch kein offizielles stabiles Release.

Der aktuelle Repository-Zustand hat daher absichtlich:

* keine offizielle stabile Release-Version
* keinen Release-Tag
* kein GitHub-Release

Die aktuellen Komponentenversionen umfassen:

* LUMS Agent: `1.7.0`
* LUMS Watcher: `1.2.1`

Es gibt derzeit keine einzelne formale Versionsnummer, die die vollständige LUMS-Anwendung repräsentiert.

Dies ist eine beabsichtigte Projektzustandsentscheidung und keine versehentliche Auslassung.

Der geplante Release-Prozess ist:

1. Implementierungsarbeit abschließen.
2. Sicherheitsüberprüfung abschließen.
3. Die Dokumentation überprüfen und synchronisieren.
4. Die vollständige automatisierte Testsuite abschließen.
5. CI verifizieren.
6. Die Release-Version definieren.
7. Den entsprechenden Git-Tag erstellen.
8. Das GitHub-Release veröffentlichen.
9. Das Release als dokumentierte Basis bewahren.

Es wird kein offizielles Release allein deshalb erstellt, weil das Sicherheitsaudit eine bestimmte Auditnummer erreicht.

Die Release-Erstellung erfolgt erst, nachdem die verbleibende Implementierungs- und Dokumentationsarbeit abgeschlossen wurde.

**Status: ÜBERPRÜFT — DESIGNBEDINGT OFFEN**

---

# Auditstatus nach Teil 5

Die folgenden Sicherheitsauditbereiche sind abgeschlossen:

| Audit | Bereich                                | Status                    |
| ----- | -------------------------------------- | ------------------------- |
| #01   | SQLite-Fremdschlüssel                  | BESTANDEN                 |
| #02   | SQLite-Laufzeitkonfiguration           | BESTANDEN                 |
| #03   | Update-Timeout / Prozessbehandlung     | BESTANDEN                 |
| #04   | Login-Ratenbegrenzung                  | BESTANDEN                 |
| #05   | API-Eingabevalidierung                 | BESTANDEN                 |
| #06   | Sitzungswiderruf                       | BESTANDEN                 |
| #07   | Client-Token-Rotation                  | BESTANDEN                 |
| #08   | IP-Adressbehandlung / Offline-Netzwerke | BESTANDEN                |
| #09   | Job-Wiederherstellung / Checkpointing  | BESTANDEN                 |
| #10   | APT-Robustheit                         | BESTANDEN                 |
| #11   | Arch-Reboot-Erkennung                  | BESTANDEN                 |
| #12   | Unit-Tests / API-Ergebnisvalidierung   | BESTANDEN                 |
| #13   | Simulationstests                       | BESTANDEN                 |
| #14   | Kontinuierliche Integration            | BESTANDEN                 |
| #15   | Anwendungs-/Audit-Logging              | BESTANDEN                 |
| #16   | Versionierung / Releases               | ÜBERPRÜFT — DESIGNBEDINGT OFFEN |

Der verbleibende nummerierte technische Auditbereich ist:

* #17 Rollenbasierte Zugriffskontrolle

Die Dokumentationsüberprüfung wird separat verfolgt als:

* #18 Dokumentationsüberprüfung — IN BEARBEITUNG

# Sicherheitsaudit #17

## Rollenbasierte Zugriffskontrolle

LUMS kombiniert Rollenvorlagen mit individuell zugewiesenen Berechtigungen. Die unterstützten Vorlagen sind `administrator`, `operator` und `viewer`; die Auswahl einer Vorlage wählt deren Standardberechtigungen, die ein Administrator für jedes Konto anpassen kann.

Die Rolle bleibt Kontometadata. Geschützte Routen autorisieren gegen den serverseitig gespeicherten Berechtigungssatz des Kontos, nicht gegen die Rollenbezeichnung. Die Oberfläche blendet nicht verfügbare Funktionen aus Gründen der Benutzerfreundlichkeit aus, während der Server die Sicherheitsgrenze bleibt.

---

## RBAC-Berechtigungsmodell

| Berechtigung      | Gewährter Zugriff |
| ----------------- | ----------------- |
| `clients.view`    | Clients und Systeminformationen anzeigen |
| `software.view`   | Installierte Software anzeigen |
| `updates.view`    | Verfügbare Updates, Jobs und Verlauf anzeigen |
| `packages.search` | Paket-Repositories durchsuchen |
| `jobs.manage`     | Paketoperationen und Update-Jobs erstellen |
| `clients.manage`  | Clients registrieren/entfernen und Client-Tokens rotieren |
| `users.manage`    | Benutzer erstellen und Rollen und Berechtigungen verwalten |

Die Standard-Rollenvorlagen sind:

| Vorlage         | Standardberechtigungen |
| --------------- | ---------------------- |
| `administrator` | Alle Berechtigungen    |
| `operator`      | Client-/Software-/Update-Sichtbarkeit, Paketsuche und Job-Verwaltung |
| `viewer`        | Client-Sichtbarkeit und Sichtbarkeit installierter Software |

Client-bezogene Berechtigungen erfordern `clients.view`. `jobs.manage` erfordert außerdem `updates.view`. Die UI lädt Berechtigungen für das authentifizierte Konto und lässt Steuerelemente weg, die der Benutzer nicht verwenden kann; serverseitige Prüfungen setzen unabhängig dieselben Gewährungen durch.

---

## Autorisierungsdurchsetzung

Geschützte Operationen verwenden serverseitige Authentifizierungs- und Berechtigungsprüfungen.

Das Autorisierungsmodell folgt dem Prinzip:

`Authenticate → Load User Permissions → Authorize Operation → Execute`

Authentifizierung allein ist nicht ausreichend, um auf privilegierte Operationen zuzugreifen.

Zustandsändernde Operationen erfordern zusätzlich CSRF-Schutz, wo anwendbar.

Beispiele geschützter administrativer Operationen umfassen:

* Update-Job-Erstellung
* Paketinstallation
* Paketentfernung
* Paket-Updates
* Systemupdates
* paketverwaltungsbezogene Operationen
* Client-Erstellung
* Client-Deaktivierung
* Client-Token-Rotation
* Benutzererstellung
* Benutzerverwaltungsfunktionen

Geschützte Endpunkte definieren ausdrücklich die für die entsprechende Operation erforderliche Berechtigung.

Eine fehlende Berechtigung wird vom Server abgelehnt, selbst wenn der Benutzer die entsprechende HTTP-Anfrage manuell konstruiert.

Dies verhindert die Umgehung des RBAC-Modells durch direktes Aufrufen eines API-Endpunkts, der in der Weboberfläche ausgeblendet ist.

---

## Viewer-Einschränkungen

Die Viewer-Vorlage ist durch ihren Standardberechtigungssatz absichtlich eingeschränkt.

Für Konten ohne die entsprechenden Gewährungen zeigt die Client-Oberfläche nicht:

* Updates
* Update-Jobs
* Update-Verlauf
* Paketverwaltung
* Systemwartung

Der Server verhindert zusätzlich, dass Konten ohne die entsprechenden Gewährungen geschützte Operationen durchführen.

Die JavaScript-Oberfläche lädt keine Update-Management-Daten ohne `updates.view`.

Dies reduziert die unnötige Exposition operativer Informationen, während die serverseitige Autorisierung als tatsächliche Sicherheitskontrolle erhalten bleibt.

Installierte Software bleibt für Viewer-Konten als schreibgeschützte Informationsfunktion verfügbar.

---

## Administrative Benutzerverwaltung

Die Benutzerverwaltung erfordert die Berechtigung `users.manage`.

Benutzer mit dieser Berechtigung können Konten ohne Berechtigungen erstellen und dann individuelle Gewährungen zuweisen oder eine Rollenvorlage im Berechtigungseditor anwenden. Rollenvorlagen haben Beschreibungen, die ihre Standardgewährungen erklären.

Autorisierte Benutzermanager können eine interne Notiz pro Konto speichern. Notizen sind auf 2.000 Zeichen beschränkt, sind nicht in Audit-Log-Details enthalten und sind für den Kontoinhaber nicht sichtbar.

Die Benutzererstellung umfasst:

* Benutzernamenvalidierung
* Rollenvalidierung
* Passwortvalidierung
* Argon2-Passwort-Hashing
* Duplikat-Benutzer-Erkennung
* Audit-Logging
* CSRF-Schutz
* serverseitige Autorisierung

Benutzerverwaltungsendpunkte sind ohne `users.manage` nicht zugänglich.

Der Server lehnt unbekannte Berechtigungen und ungültige Abhängigkeitskombinationen ab. Mindestens ein aktives Konto muss `users.manage` behalten; Änderungen, die den letzten Benutzermanager entfernen würden, werden abgelehnt.

Passwörter werden niemals im Klartext gespeichert.

---

## RBAC-Datenbankmigration

Rollenvorlageninformationen bleiben im Benutzerdatenbankdatensatz. Individuelle Gewährungen werden in der Tabelle `user_permissions` mit einem Fremdschlüssel zum Benutzerkonto gespeichert. Die Migration `003-user-permissions` erstellt diese Tabelle und befüllt bestehende Konten aus ihrer aktuellen Rollenvorlage, wodurch ihr Zugriff während des Übergangs bewahrt wird. Die Migration `004-user-admin-notes` fügt das private Feld `users.admin_note` hinzu; bestehende Konten erhalten eine leere Notiz. Die Migration `005-backup-permission` gewährt `backups.manage` an bestehende Administratorkonten.

Die Datenbank-Backup-Erstellung erfordert `backups.manage`; die Administrator-Vorlage enthält diese Berechtigung standardmäßig. Der Server schreibt SQLite-Online-Backups nur in das vom Server konfigurierte `LUMS_BACKUP_DIR`; er akzeptiert keine Dateisystempfade vom Browser. Backup-Dateien werden mit Nur-Eigentümer-Berechtigungen erstellt und vor der Veröffentlichung auf Integrität geprüft.

---

## RBAC-Sicherheitstests

RBAC-Verhalten ist durch automatisierte Tests abgedeckt.

Die Tests umfassen:

* Administrator-Autorisierung
* Operator-Autorisierung
* Viewer-Einschränkungen
* geschützter API-Zugriff
* nicht autorisierte Operationen
* Client-Management-Einschränkungen
* Update-Job-Einschränkungen
* Benutzerverwaltungseinschränkungen
* Client-Seiten-Sichtbarkeit
* berechtigungsspezifisches Schnittstellenverhalten

RBAC-Tests decken Rollenvorlagen-Standardwerte, benutzerdefinierte Berechtigungen, Berechtigungsabhängigkeiten und serverseitige Autorisierung ab. Die Produktionsverifikation sollte Konten mit angepassten Berechtigungen sowie die Standardvorlagen Administrator, Operator und Viewer umfassen.

---

## RBAC-Sicherheitsergebnis

Die RBAC-Implementierung bietet geschichtete Autorisierung:

1. Die Authentifizierung stellt die Benutzeridentität fest.
2. Der Server lädt die Berechtigungen des Benutzers.
3. Geschützte Routen setzen die erforderliche Berechtigung durch.
4. Der CSRF-Schutz gilt für relevante Browser-Zustandsänderungen.
5. Die Weboberfläche blendet nicht verfügbare Funktionalität aus.
6. Automatisierte Tests verifizieren Autorisierungsgrenzen.

Die Oberfläche bietet daher nicht selbst den Autorisierungsmechanismus.

Der Server bleibt die maßgebliche Sicherheitsgrenze.

**Status: BESTANDEN**

# Sicherheitsaudit #18

## Dokumentationsüberprüfung

Die Sicherheitsdokumentation wird gegen das aktuell implementierte LUMS-System überprüft.

Der Zweck dieser Überprüfung ist sicherzustellen, dass die Sicherheitsdokumentation die tatsächliche Implementierung beschreibt und nicht einen früheren Entwicklungszustand.

Die Überprüfung umfasst:

* Authentifizierung
* Autorisierung
* RBAC
* Client-Authentifizierung
* Token-Behandlung
* Sitzungsbehandlung
* CSRF-Schutz
* Ratenbegrenzung
* SQLite-Konfiguration
* Update-Ausführung
* Job-Wiederherstellung
* Paketverwaltung
* Container-Härtung
* Netzwerkexposition
* Secrets-Behandlung
* Abhängigkeits- und Build-Sicherheit
* Dateisystemberechtigungen
* Anwendungs- und Audit-Logging
* Versionierung und Release-Behandlung
* automatisierte Sicherheitstests

Die Dokumentation muss unterscheiden zwischen:

* implementierten Kontrollen
* verifiziertem Produktionsverhalten
* geplanten Verbesserungen
* absichtlich offenen Projektentscheidungen

Historische Implementierungsdetails dürfen nicht als aktuelle Produktionskonfiguration dargestellt werden.

Insbesondere spiegelt die Dokumentation die aktuelle SQLite-Produktionskonfiguration wider.

Die aktuelle Produktionslaufzeit ist dokumentiert als:

* `journal_mode = wal`
* `busy_timeout = 5000`
* `synchronous = 2`
* `PRAGMA foreign_keys = ON` auf Anwendungsebene

Das aktuelle Viewer-RBAC-Verhalten ist ebenfalls gemäß der implementierten Produktionsoberfläche dokumentiert.

Viewer-Benutzer haben Zugriff auf:

* Client-Informationen
* installierte Software

Viewer-Benutzer haben keinen Zugriff auf:

* Updates
* Update-Jobs
* Update-Verlauf
* Paketverwaltung
* Systemwartung

Die Dokumentationsüberprüfung entfernt oder ersetzt auch veraltete Referenzen auf frühere Testanzahlen, Migrationszustände, Bereitstellungskonfigurationen und reine Entwicklungsverhalten.

**Status: IN BEARBEITUNG**

---

# Zusätzliche Sicherheitshärtung

Das nummerierte Sicherheitsaudit deckt die primären Anwendungssicherheitskontrollen ab.

Zusätzliche Härtung wurde nach der ursprünglichen Auditsequenz durchgeführt und ist Teil der aktuellen Sicherheitsbasis.

Diese Kontrollen sind hier dokumentiert, weil sie wichtige Sicherheitseigenschaften der aktuellen Bereitstellung repräsentieren.

---

## Container-Härtung

Der LUMS-Produktionscontainer läuft mit einer gehärteten Docker-Konfiguration.

Der Produktionscontainer verwendet:

* Non-Root-Anwendungsbenutzer
* schreibgeschütztes Root-Dateisystem
* verworfene Linux-Capabilities
* `no-new-privileges`
* eingeschränkte temporäre Dateisysteme
* schreibgeschützter Secret-Mount
* dediziertes persistentes Anwendungsdaten-Volume
* Restart-Richtlinie
* Loopback-only-Host-Veröffentlichung des Anwendungsports

Das Anwendungs-Root-Dateisystem ist daher während des normalen Betriebs nicht beschreibbar.

Beschreibbare Speicherorte sind ausdrücklich auf die von der Anwendung benötigten Speicherorte beschränkt.

Der Produktionscontainer wurde unabhängig inspiziert, um die effektive Laufzeitkonfiguration zu verifizieren.

Die gehärtete Laufzeit wurde auch getestet durch Verifikation, dass:

* Anwendungsdateisystem-Schreibvorgänge fehlschlagen
* `/tmp` verfügbar bleibt, wo erforderlich
* `/var/lib/lums` beschreibbar bleibt
* die Secret-Datei schreibgeschützt bleibt
* die Anwendung operativ bleibt

---

## Netzwerkexposition

Der LUMS-Anwendungsport ist nicht direkt dem LAN ausgesetzt.

Der Docker-Anwendungsport ist an die Loopback-Schnittstelle gebunden:

`127.0.0.1:5050`

Externer Zugriff wird über Nginx bereitgestellt.

Der Produktionshost stellt die vorgesehenen Netzwerkdienste über die Firewall und den Reverse-Proxy bereit.

Die Bereitstellung wurde verifiziert, um direkten Remote-Zugriff auf den internen Docker-Anwendungsport zu verhindern.

Die Firewall verwendet ein Default-Deny-Modell für eingehenden und gerouteten Verkehr.

Die vorgesehenen extern erreichbaren Dienste sind:

* SSH
* HTTP
* HTTPS

HTTP-Anfragen werden vom Webserver auf HTTPS weitergeleitet.

Die Standard-Nginx-Site wurde entfernt, sodass unzusammenhängender Standardinhalt nicht exponiert wird.

---

## Transportsicherheit

Administrativer Webzugriff wird über HTTPS bereitgestellt.

HTTP wird auf HTTPS weitergeleitet.

Der TLS-Endpunkt wird von Nginx statt direkt von der Flask/Gunicorn-Anwendung behandelt.

Dies hält Transportsicherheit und Anwendungsauslieferung getrennt.

Der interne Gunicorn-Anwendungsport ist daher nicht als öffentlicher HTTP-Endpunkt vorgesehen.

Die aktuelle Bereitstellung ist für kontrollierte interne Infrastruktur vorgesehen.

Eine zukünftige Bereitstellung mit direkter öffentlicher Internet-Exposition würde eine zusätzliche Sicherheitsüberprüfung erfordern.

---

## Secrets und Konfiguration

Produktionssecrets werden nicht im Anwendungsquellbaum gespeichert.

Der LUMS-Secret-Key wird über eine geschützte Secret-Datei bereitgestellt.

Der Produktionscontainer erhält das Secret über:

`/run/secrets/lums_secret`

Die Secret-Datei wird schreibgeschützt gemountet.

Die Anwendung liest das Secret über den konfigurierten Secret-Datei-Mechanismus.

Die Behandlung von Repository und Docker-Build-Kontext wurde überprüft, um versehentliche Aufnahme von Folgendem zu verhindern:

* Datenbankdateien
* Backup-Dateien
* Secret-Dateien
* privaten Schlüsseln
* Zertifikaten
* Laufzeitlogs
* lokalen Backup-Artefakten

Das Repository ignoriert auch gängige temporäre Backup-Muster, die während der Entwicklung verwendet werden.

---

## Abhängigkeits- und Build-Sicherheit

Das Produktions-Docker-Image verwendet einen gepinnten Python-Basisimage-Digest.

Die Produktionslaufzeitabhängigkeiten sind ausdrücklich versionsgepinnt.

Der aktuelle Produktionsabhängigkeitssatz umfasst:

* Flask `3.1.3`
* argon2-cffi `25.1.0`
* Gunicorn `23.0.0`

Der Docker-Build-Kontext wird durch `.dockerignore` eingeschränkt.

Wiederholte Produktionsbuilds wurden während des Audits verglichen.

Die relevanten Abhängigkeits- und Paketmetadaten blieben zwischen wiederholten Builds konsistent, abgesehen von erwarteten generierten Python-Bytecode-Unterschieden.

Dies bietet eine reproduzierbare Basis für das Produktionsimage, während der Build-Kontext begrenzt bleibt.

---

## Dateisystem- und Laufzeitberechtigungen

Die Produktionsanwendung läuft als dedizierter `lums`-Benutzer statt als Root.

Persistente Anwendungsdaten werden im dedizierten LUMS-Daten-Volume gespeichert.

Das Anwendungs-Root-Dateisystem ist schreibgeschützt.

Laufzeitschreibzugriff ist auf ausdrücklich erforderliche Speicherorte beschränkt.

Die Produktionslaufzeit wurde verifiziert, um nicht autorisierte Schreibvorgänge auf das Anwendungsdateisystem abzulehnen.

Dies reduziert die Auswirkung versehentlicher oder böswilliger Dateimodifikation innerhalb des Anwendungscontainers.

---

# Abschluss des Sicherheitsaudits

Die aktuelle LUMS-Implementierung hat eine breite Sicherheitsüberprüfung durchlaufen, die abdeckt:

* Authentifizierung
* Autorisierung
* RBAC
* Sitzungssicherheit
* CSRF-Schutz
* Login-Ratenbegrenzung
* Client-Token-Sicherheit
* API-Validierung
* SQL-Injection-Widerstand
* SQLite-Integrität
* Update-Ausführung
* Timeout-Behandlung
* Job-Wiederherstellung
* Paketverwaltungs-Robustheit
* Ergebnisvalidierung
* Simulation
* kontinuierliche Integration
* Audit-Logging
* Container-Härtung
* Netzwerkexposition
* Transportsicherheit
* Secrets-Behandlung
* Dateisystemberechtigungen
* Abhängigkeits- und Build-Sicherheit

Die nummerierten Auditergebnisse sind:

| Audit | Bereich                                | Status                    |
| ----- | -------------------------------------- | ------------------------- |
| #01   | SQLite-Fremdschlüssel                  | BESTANDEN                 |
| #02   | SQLite-Laufzeitkonfiguration           | BESTANDEN                 |
| #03   | Update-Timeout / Prozessbehandlung     | BESTANDEN                 |
| #04   | Login-Ratenbegrenzung                  | BESTANDEN                 |
| #05   | API-Eingabevalidierung                 | BESTANDEN                 |
| #06   | Sitzungswiderruf                       | BESTANDEN                 |
| #07   | Client-Token-Rotation                  | BESTANDEN                 |
| #08   | IP-Adressbehandlung / Offline-Netzwerke | BESTANDEN                |
| #09   | Job-Wiederherstellung / Checkpointing  | BESTANDEN                 |
| #10   | APT-Robustheit                         | BESTANDEN                 |
| #11   | Arch-Reboot-Erkennung                  | BESTANDEN                 |
| #12   | Unit-Tests / API-Ergebnisvalidierung   | BESTANDEN                 |
| #13   | Simulationstests                       | BESTANDEN                 |
| #14   | Kontinuierliche Integration            | BESTANDEN                 |
| #15   | Anwendungs-/Audit-Logging              | BESTANDEN                 |
| #16   | Versionierung / Releases               | ÜBERPRÜFT — DESIGNBEDINGT OFFEN |
| #17   | Rollenbasierte Zugriffskontrolle       | BESTANDEN                 |
| #18   | Dokumentationsüberprüfung              | IN BEARBEITUNG            |

Die technischen Sicherheitskontrollen, die in den Audits #01–#15 und #17 überprüft wurden, sind bestanden.

Audit #16 bleibt absichtlich offen, weil LUMS noch nicht sein erstes offizielles stabiles Release erreicht hat.

Audit #18 bleibt offen, bis die vollständige Projektdokumentation überprüft und mit dem endgültigen Implementierungszustand synchronisiert wurde.

Kein Sicherheitsauditergebnis sollte als Garantie interpretiert werden, dass LUMS frei von Schwachstellen ist.

Sicherheit ist ein fortlaufender Prozess.

Änderungen an der Anwendung, am Agent, an Abhängigkeiten, an der Container-Konfiguration, an der Netzwerkexposition, am Authentifizierungsmodell oder an der Bereitstellungsarchitektur sollten eine erneute Sicherheitsüberprüfung der betroffenen Kontrollen auslösen.

---

# Sicherheitsbasis

Die aktuelle Sicherheitsbasis basiert auf der verifizierten Implementierung und dem Produktionsbereitstellungszustand.

Die Basis umfasst:

* serverseitige Authentifizierung
* serverseitige RBAC
* Argon2-Passwort-Hashing
* SHA-256-Client-Token-Digests
* CSRF-Schutz
* Login-Ratenbegrenzung
* parametrisiertes SQL
* validierte API-Eingabe
* kontrollierte Paketmanager-Ausführung
* Update-Job-Wiederherstellung
* Audit-Logging
* gehärtete Docker-Laufzeit
* HTTPS über Nginx
* Loopback-only-Anwendungsport-Exposition
* Firewall-Einschränkungen
* geschützte Produktionssecrets
* gepinnte Produktionsabhängigkeiten
* eingeschränkte Dateisystemberechtigungen
* automatisierte Sicherheitstests

Zukünftige Änderungen sollten diese Eigenschaften bewahren, es sei denn, eine bewusste architektonische Änderung ersetzt sie durch eine gleichwertige oder stärkere Kontrolle.

---

# Sicherheitswartung

Sicherheitskontrollen sollten erneut validiert werden, wenn signifikante Änderungen eingeführt werden.

Beispiele umfassen:

* Authentifizierungsänderungen
* neue Benutzerrollen
* neue API-Endpunkte
* Paketverwaltungsänderungen
* Agent-Ausführungsänderungen
* Datenbankmigrationen
* Abhängigkeitsupdates
* Dockerfile-Änderungen
* Container-Laufzeitänderungen
* Reverse-Proxy-Änderungen
* Firewall-Änderungen
* Secret-Management-Änderungen
* Release-Vorbereitung

Sicherheitstests sollten vor der Veröffentlichung eines offiziellen Releases durchgeführt werden.

Die Sicherheitsdokumentation sollte aktualisiert werden, wann immer sich die verifizierte Sicherheitsbasis ändert.

---

# Release-Bereitschaft

Das erste offizielle LUMS-Release wird erst erstellt, nachdem:

1. die Implementierungsarbeit abgeschlossen ist
2. die Sicherheitsüberprüfung abgeschlossen ist
3. die Dokumentationsüberprüfung abgeschlossen ist
4. die vollständige automatisierte Testsuite besteht
5. CI besteht
6. die endgültige Version definiert ist
7. der Git-Tag erstellt ist
8. das GitHub-Release veröffentlicht ist

Bis dahin bleibt LUMS ein aktiv entwickeltes Projekt.

---

# Abschließende Erklärung

LUMS ist als kontrollierte Linux-Update-Management-Plattform konzipiert, bei der Sicherheit ein zentrales architektonisches Anliegen ist.

Das Sicherheitsmodell verlässt sich nicht auf einen einzelnen Schutzmechanismus.

Stattdessen arbeiten Authentifizierung, Autorisierung, Validierung, kontrollierte Ausführung, Persistenz, Wiederherstellung, Logging, Container-Isolation, Netzwerkeinschränkungen und automatisierte Tests als geschichtete Kontrollen zusammen.

Das Projekt bevorzugt bewusst ausdrückliche serverseitige Durchsetzung gegenüber Security-by-Interface.

Die aktuelle Sicherheitsbasis ist gemäß dem verifizierten Implementierungszustand dokumentiert und nicht gemäß historischem Entwicklungsverhalten.

---

**LUMS — Linux Update Management ohne das Rauschen.**

`segfault // override`
