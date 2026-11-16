# LUMS SOC – Anforderungen an Collector-mTLS und Gateway

Status: Planung
Implementierungsstatus: Nicht umgesetzt
Teststatus: Nicht getestet

## 1. Ziel

Die Kommunikation unabhängiger LUMS-SOC-Collector muss durch
gegenseitige TLS-Authentifizierung (mTLS) abgesichert werden.

Die bestehende Collector-Registrierung, SHA-256-Zertifikatsidentität
und Sperrlogik bleiben erhalten.

Die Authentifizierung muss erfolgen, bevor ein Collector Ereignisse
an die LUMS-Anwendung übermitteln kann.

## 2. Zielarchitektur

Vorgesehene Komponenten:

- Separater Nginx-Gateway-Container
- LUMS-Flask-Backend als eigener Container
- Isoliertes internes Docker-Netzwerk zwischen Gateway und Backend
- Separates Zertifikatsverzeichnis für die vertrauenswürdige Client-CA
- Persistente LUMS-Datenbank mit Collector-Registrierung
- Bestehender SOC-Worker als unabhängiger Prozess

Datenfluss:

Collector
  -> HTTPS mit verpflichtendem mTLS
  -> Nginx-Gateway
  -> authentifizierte Collector-Identität
  -> internes Docker-Netzwerk
  -> LUMS-Flask-Backend
  -> CollectorStore
  -> SOC-Event-Inbox
  -> SOC-Worker

Der SOC-Worker erhält keine direkte Netzwerkverbindung zu Collectors.

## 3. Anforderungen an mTLS

- Client-Zertifikate müssen von einer ausdrücklich konfigurierten
  vertrauenswürdigen CA stammen.
- Nginx muss Client-Zertifikate verpflichtend prüfen.
- Nicht vertrauenswürdige, fehlende oder ungültige Zertifikate
  müssen bereits am Gateway abgewiesen werden.
- Zertifikatsgültigkeit und Zertifikatskette müssen geprüft werden.
- Zertifikatswiderruf über CRL ist als zusätzliche Schutzmaßnahme
  zu prüfen und zu dokumentieren.
- Zertifikatsidentitäten dürfen nicht anhand des CN oder eines
  frei übermittelten Agent-Namens bestimmt werden.
- Die Collector-Identität wird über den SHA-256-Fingerabdruck
  des verifizierten Zertifikats bestimmt.
- Nginx' Standardvariable $ssl_client_fingerprint darf nicht
  ungeprüft verwendet werden, da sie einen SHA-1-Fingerabdruck
  liefert und die Anwendung SHA-256 erwartet.

## 4. Vertrauensgrenze zwischen Nginx und Flask

- Das Backend darf nicht direkt aus dem öffentlichen Netz erreichbar sein.
- Der Backend-Port 5000 darf nicht öffentlich veröffentlicht werden.
- Gateway und Backend kommunizieren ausschließlich über ein
  dediziertes internes Docker-Netzwerk.
- Nur der vorgesehene Gateway-Container darf dieses Netzwerk nutzen.
- Eingehende, vom Client gesetzte Identitätsheader müssen am Gateway
  entfernt und durch vertrauenswürdige Werte ersetzt werden.
- Die Anwendung darf Identitätsheader nur akzeptieren, wenn die
  Verbindung nachweislich aus der festgelegten Proxy-Vertrauenszone kommt.
- Die Anwendung darf niemals einen Agent-Namen oder Fingerabdruck
  aus dem JSON-Request-Body als Authentifizierungsnachweis verwenden.
- Proxy-Vertrauen muss explizit konfiguriert und darf nicht pauschal
  auf beliebige Proxy-Adressen erweitert werden.
- Eine zusätzliche Authentifizierung zwischen Gateway und Backend
  ist als Defense-in-Depth-Maßnahme zu bewerten.

## 5. Ermittlung des SHA-256-Fingerabdrucks

Bevorzugte Planungsvariante:

- Nginx prüft die Client-Zertifikatskette mittels mTLS.
- Das verifizierte Zertifikat wird über einen festgelegten,
  vom Gateway überschriebenen internen Header weitergegeben.
- Das Backend akzeptiert diesen Header ausschließlich aus der
  vertrauenswürdigen Gateway-Verbindung.
- Flask beziehungsweise eine geeignete Zertifikatsbibliothek
  extrahiert das Zertifikat und berechnet den SHA-256-Fingerabdruck.
- Die Zertifikatsdaten müssen sicher und eindeutig geparst werden.
- Ungültige, fehlende oder mehrdeutige Zertifikatsdaten führen
  zur Ablehnung der Anfrage.
- Header-Größenlimits müssen berücksichtigt werden.
- Zertifikatsdaten dürfen nicht unnötig protokolliert werden.

Vor Implementierung sind die konkrete Nginx-Variable,
PEM-Kodierung, Header-Weitergabe und Flask-Verarbeitung anhand
der offiziellen Dokumentation zu verifizieren.

## 6. Bestehende Collector-Registrierung

Die bestehende Implementierung in server/soc/collector_store.py
bleibt die maßgebliche Registrierungsinstanz.

Beizubehalten sind:

- Eindeutige agent_id
- Eindeutiger certificate_sha256
- SHA-256-Validierung mit 64 Hex-Zeichen
- Registrierung ausschließlich durch vertrauenswürdige
  administrative Funktionen
- Keine Selbstregistrierung durch Collector-Requests
- Keine Übernahme einer Agent-Identität aus dem Request-Body

Die Datenbank bleibt maßgeblich für die Zuordnung von Zertifikat
und Collector.

## 7. Sperrung und Zertifikatswechsel

Die bestehende Sperrlogik bleibt erhalten:

- status = active oder revoked
- revoked_at dokumentiert den Sperrzeitpunkt
- Gesperrte Collector dürfen keine Ereignisse einliefern.
- Die Prüfung muss bei jeder Event-Annahme erfolgen.
- Ein bereits auf TLS-Ebene gültiges Zertifikat darf eine
  Anwendungssperre nicht umgehen.

Für Zertifikatswechsel ist ein administrativer Prozess festzulegen:

- Neues Zertifikat ausstellen
- Neuen SHA-256-Fingerabdruck registrieren
- Übergangsphase ausdrücklich definieren
- Altes Zertifikat sperren
- Wechsel nachvollziehbar protokollieren

Es darf keine automatische Freigabe eines neuen Zertifikats
allein aufgrund einer bekannten agent_id geben.

## 8. Collector-API

Der bestehende Endpunkt /api/collector/v1/events bleibt erhalten.

Beizubehalten sind:

- Explizite Aktivierung der Collector-API
- Authentifizierung vor der Event-Verarbeitung
- Prüfung der Collector-Registrierung
- Prüfung des Sperrstatus
- Begrenzung der Request-Größe
- Begrenzung der Batch-Größe
- Vollständige Validierung des Batches vor Persistierung
- Atomare Speicherung
- Idempotenz anhand von Collector-ID und Event-ID
- Konflikterkennung bei wiederverwendeten Event-IDs
- Keine Verarbeitung bei fehlender oder ungültiger Identität

## 9. Docker- und Laufzeitanforderungen

- Gateway und Backend werden getrennt betrieben.
- Das Backend erhält keinen öffentlich erreichbaren Port.
- Der Gateway-Container veröffentlicht ausschließlich den
  vorgesehenen HTTPS-Port.
- Das Backend bleibt unprivilegiert.
- Read-only Root Filesystem bleibt erhalten, soweit technisch möglich.
- Linux-Capabilities werden weiterhin minimiert.
- no-new-privileges bleibt aktiviert.
- Zertifikate und private Schlüssel werden nicht in Images eingebaut.
- Private Schlüssel werden nur über geeignete Secret-Mounts bereitgestellt.
- Zertifikatsverzeichnisse erhalten restriktive Berechtigungen.
- Persistente LUMS-Daten bleiben vom Container-Lebenszyklus getrennt.
- Healthchecks müssen Gateway und Backend getrennt prüfen.
- Logs dürfen keine privaten Schlüssel oder vollständigen
  Client-Zertifikate offenlegen.

## 10. Konfigurationsanforderungen

Vor Implementierung festzulegen:

- Pfad zur vertrauenswürdigen Client-CA
- Pfad zu einer optionalen CRL
- TLS-Protokoll- und Cipher-Vorgaben
- Externer HTTPS-Listener
- Interner Backend-Endpunkt
- Vertrauenswürdige Proxy-Verbindung
- Header-Name und Format der Zertifikatsweitergabe
- Request- und Header-Größenlimits
- Zertifikatswechselprozess
- Verhalten bei CA- oder CRL-Ausfall
- Verhalten bei nicht erreichbarem Backend

Sicherheitsrelevante Einstellungen müssen fail-closed sein.

## 11. Protokollierung und Audit

Zu protokollieren sind mindestens:

- Erfolgreiche Collector-Authentifizierung
- Abgelehnte Zertifikate
- Unbekannte Collector
- Gesperrte Collector
- Administrative Registrierung
- Administrative Sperrung
- Zertifikatswechsel
- Fehler bei der Zertifikatsprüfung

Nicht protokolliert werden dürfen:

- Private Schlüssel
- Collector-Secrets
- Vollständige sensible Zertifikatsinhalte
- Ungefilterte Event-Payloads mit möglicherweise vertraulichen Daten

## 12. Erforderliche Tests vor Freigabe

Gateway und mTLS:
- Anfrage ohne Client-Zertifikat wird abgewiesen.
- Zertifikat einer unbekannten CA wird abgewiesen.
- Abgelaufenes Zertifikat wird abgewiesen.
- Ungültige Zertifikatskette wird abgewiesen.
- Gültiges Zertifikat wird korrekt identifiziert.
- SHA-256-Fingerabdruck stimmt mit dem registrierten Wert überein.

Proxy-Vertrauensgrenze:
- Gefälschte Client-Identitätsheader werden überschrieben.
- Direkter Zugriff auf das Backend ist nicht möglich.
- Nicht vertrauenswürdige Container können das Backend nicht erreichen.
- Fehlende Proxy-Identität führt zur Ablehnung.
- Unzulässige Zertifikatsheader werden abgewiesen.

Collector-Registrierung:
- Registriertes Zertifikat wird akzeptiert.
- Unbekanntes Zertifikat wird abgewiesen.
- Gesperrter Collector wird abgewiesen.
- Zertifikatswechsel funktioniert nach dem festgelegten Prozess.
- Doppelte Registrierung bleibt ausgeschlossen.

Event-Verarbeitung:
- Gültige Events werden angenommen.
- Wiederholte identische Events bleiben idempotent.
- Wiederverwendete Event-ID mit verändertem Inhalt wird abgewiesen.
- Ungültige Batches werden vollständig abgewiesen.
- Größenlimits werden eingehalten.

Betrieb:
- Gateway-Neustart
- Backend-Neustart
- Worker-Neustart
- CA-/CRL-Ausfall
- Datenbank nicht erreichbar
- Container-Rebuild ohne Verlust persistenter Daten

## 13. Freigabekriterien

Eine Implementierung gilt erst als freigabefähig, wenn:

- Alle Anforderungen technisch umgesetzt oder begründet ausgeschlossen sind.
- Die Vertrauensgrenze zwischen Gateway und Backend nachgewiesen ist.
- Kein direkter ungeschützter Backend-Zugriff möglich ist.
- Alle sicherheitsrelevanten Negativtests bestehen.
- Die bestehende Collector-Registrierung und Sperrlogik erhalten bleiben.
- Die vollständige Testsuite erfolgreich ist.
- Docker-Härtung und persistente Datenhaltung erhalten bleiben.
- Deployment und Rollback dokumentiert sind.

## 14. Abgrenzung

Dieses Dokument ist eine Anforderungsspezifikation.

Es autorisiert ausdrücklich noch nicht:

- Änderungen am Anwendungscode
- Änderungen an Datenbankschemata oder Migrationen
- Änderungen am Docker-Deployment
- Änderungen am Testcontainer
- Änderungen an Produktionscontainern oder Produktionsdaten
- Start des SOC-Workers
- Produktivsetzung der mTLS-Verbindung

Die Implementierung beginnt erst nach abgeschlossener Planung
und ausdrücklicher Freigabe der nächsten Arbeitsphase.
