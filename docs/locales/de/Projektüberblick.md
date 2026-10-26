
# LUMS

**Linux-Updateverwaltung ohne unnötigen Lärm.**

## Erste Schritte

LUMS verwaltet Linux-Updates zentral. Ein Server zeigt Clients, installierte Software und verfügbare Updates an. Ein Agent auf jedem verwalteten Linux-System führt genehmigte Paketaktionen mithilfe des Paketmanagers dieses Systems aus. LUMS ersetzt weder APT unter Debian/Ubuntu noch pacman unter Arch Linux.

**Du verwendest bereits eine bestehende LUMS-Installation?** Öffne die von deiner Administration bereitgestellte Adresse und melde dich mit deinem eigenen Konto an. Wenn eine Funktion fehlt, verfügt dein Konto möglicherweise nicht über die erforderliche Berechtigung. Bitte deine Administration um Hilfe. Teile keine Konten und verwende kein Client-Token als Webpasswort.

**Du installierst oder betreibst LUMS?** Beginne mit der [Installationsanleitung](Installation und Upgrade.md) und lies anschließend die [Administrationsanleitung](Administration und Backups.md). Wenn etwas nicht funktioniert, verwende die [Anleitung zur Fehlerbehebung](Fehlersuche.md). Übersetzte Anleitungen sind ebenfalls verfügbar; ihr Umfang kann von den englischen technischen Originalen abweichen. Das [Dokumentationsverzeichnis](../../README.md) enthält alle verfügbaren Sprachfassungen.

Ein Testlauf oder ein erfolgreich erstelltes Docker-Image ist **keine produktive Installation**. Für einen produktiven Einsatz sind außerdem HTTPS, ein geschütztes Anwendungsgeheimnis, persistente Daten, verifizierte Backups und ein gehärteter Container erforderlich. Übernimm keine Produktionsbefehle, bevor du Platzhalter und Speicherpfade mit deiner eigenen Installation abgeglichen hast.

### Sprachen der Weboberfläche

Die Weboberfläche bietet Deutsch, Englisch (USA und Großbritannien), Französisch, Spanisch, vereinfachtes Chinesisch, Japanisch, Polnisch, Schwedisch, norwegisches Bokmål und Finnisch. Wähle die Sprache oben rechts auf der Anmeldeseite. Wenn du keine Sprache auswählst, versucht LUMS, die Browsersprache zu verwenden. Nach der Anmeldung hat eine in deinem Konto gespeicherte Sprache Vorrang. Einige technische oder dynamisch erzeugte Texte können in ihrer ursprünglichen Sprache verbleiben, wenn keine Übersetzung verfügbar ist. Markdown-Anleitungen sind von der Weboberfläche getrennt und werden nicht automatisch übersetzt.

---

LUMS ist ein Linux-Updateverwaltungsserver, der eine kontrollierte, nachvollziehbare und sichere Verwaltung von Software und Updates für Linux-Clients ermöglichen soll.

Anstatt sich auf unkontrollierte Update-Aktivitäten einzelner Clients zu verlassen, bietet LUMS eine zentrale Verwaltungsebene für Softwareinventar, Update-Erkennung, Paketoperationen, Update-Aufträge, Ausführungsüberwachung und Ergebnisberichte.

LUMS ist für Umgebungen konzipiert, in denen Updates **sichtbar, kontrolliert, nachvollziehbar und wiederherstellbar** sein sollen.

---

## Was ist LUMS?

LUMS (**Linux Update Management Server**) besteht aus einem zentralen Server und schlanken Linux-Clients.

Der Server stellt die Verwaltungsoberfläche, API, Authentifizierung, Autorisierung, Auftragsverwaltung, Audit-Protokollierung und dauerhafte Speicherung bereit.

Der clientseitige Agent führt lokale Paketmanager-Operationen aus und meldet die Ergebnisse an den Server zurück.

Die grundlegende Architektur sieht folgendermaßen aus:

```text
                   ┌──────────────────────┐
                   │      Webbrowser      │
                   └──────────┬───────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │     LUMS-Server      │
                   │                      │
                   │ Weboberfläche / API  │
                   │ Authentifizierung    │
                   │ RBAC                 │
                   │ Auftragsverwaltung   │
                   │ Audit-Protokoll      │
                   │ SQLite               │
                   └──────────┬───────────┘
                              │
                        HTTPS / API
                              │
             ┌────────────────┴────────────────┐
             │                                 │
             ▼                                 ▼
     ┌─────────────────┐             ┌─────────────────┐
     │  Linux-Client   │             │  Linux-Client   │
     │                 │             │                 │
     │ LUMS-Agent      │             │ LUMS-Agent      │
     │ Paketmanager    │             │ Paketmanager    │
     │ Watcher         │             │ Watcher         │
     └─────────────────┘             └─────────────────┘
```

---

## Warum LUMS?

Linux-Systeme verfügen bereits über ausgezeichnete Paketverwaltungswerkzeuge.

LUMS versucht nicht, diese zu ersetzen.

Stattdessen ergänzt LUMS diese Werkzeuge um eine Verwaltungsebene, mit der Administratoren zentral Fragen beantworten können, zum Beispiel:

- Welche Clients gibt es?
- Welche Software ist installiert?
- Welche Updates sind verfügbar?
- Welche Pakete sollen installiert oder entfernt werden?
- Welche Update-Aufträge laufen gerade?
- Was ist während eines Updates passiert?
- Hat der Client das Ergebnis erfolgreich gemeldet?
- War ein Neustart erforderlich?
- Kann ein unterbrochener Auftrag sicher wiederhergestellt werden?
- Wer hat eine administrative Aktion ausgelöst?

Das Ziel ist nicht, den zugrunde liegenden Linux-Paketmanager zu verbergen.

Das Ziel ist, seinen Betrieb **verwaltbar und nachvollziehbar** zu machen.

---

## Kernfunktionen

### Clientverwaltung

LUMS verwaltet registrierte Linux-Clients und deren Authentifizierungsstatus.

Jeder Client erhält ein eigenes Authentifizierungs-Token.

Client-Token werden nicht als Klartext-Zugangsdaten gespeichert. Der Server speichert einen SHA-256-Hashwert und prüft eingehende Client-Authentifizierungen anhand dieses Hashwerts.

Administratoren können:

- Clients registrieren
- Clients deaktivieren
- Client-Token erneuern
- den Clientstatus prüfen
- die Rückmeldungen der Clients überwachen

---

### Softwareinventar

Clients melden ihre installierte Software an den LUMS-Server.

Der Server speichert das Inventar und stellt es über die Verwaltungsoberfläche bereit.

Die Ansicht der installierten Software ist bewusst von der Paketsuche getrennt.

So können Administratoren und Benutzer mit Leserechten installierte Software einsehen, ohne automatisch Zugriff auf Paketverwaltungsaktionen zu erhalten.

---

### Updateinventar

Clients prüfen regelmäßig, ob Paketupdates verfügbar sind.

Der Server speichert die gemeldeten Updateinformationen und stellt sie berechtigten Benutzern zur Verfügung.

Diese Informationen können als Grundlage für kontrollierte Update-Aufträge dienen.

---

### Paketverwaltung

LUMS stellt Paketverwaltungsaktionen über den Client-Agent bereit.

Zu den unterstützten Paketaktionen gehören:

- `INSTALL_PACKAGE`
- `REMOVE_PACKAGE`
- `UPDATE_PACKAGE`
- `UPDATE_SYSTEM`

Die Paketverwaltungsschicht abstrahiert den zugrunde liegenden Paketmanager.

Derzeit werden folgende Paketmanagerfamilien unterstützt:

- **Debian / Ubuntu:** APT / dpkg
- **Arch Linux:** pacman

Auch die Paketsuche ist über LUMS verfügbar.

Suchanfragen werden an den Zielclient gesendet, dort mit dem lokalen Paketmanager ausgeführt und anschließend zur Anzeige an den Server zurückgegeben.

---

### Update-Aufträge

Update-Operationen werden als persistente Aufträge dargestellt.

Ein Auftrag kann eine oder mehrere Paketoperationen enthalten und besitzt einen serverseitigen Ausführungsstatus.

Der allgemeine Lebenszyklus lautet:

```text
PENDING
   │
   ▼
RUNNING
   │
   ├──────────────► SUCCESS
   │
   └──────────────► FAILED
```

Ergebnisse auf Paketebene werden unabhängig voneinander erfasst. Dadurch können unterbrochene Aufträge wiederhergestellt werden, ohne bereits erfolgreich abgeschlossene Operationen unnötig erneut auszuführen.

---

### Kontrollierte Ausführung

LUMS führt keine beliebigen Shell-Befehle aus, die über die Weboberfläche übermittelt werden.

Der Server erstellt strukturierte Aufträge mit validierten Aktionen und Paketnamen.

Der Client-Agent ordnet diese Aktionen den passenden lokalen Paketmanager-Operationen zu.

Damit entsteht eine bewusste Trennung zwischen:

```text
Weboberfläche
   ↓
API
   ↓
Validierter Auftrag
   ↓
Agent
   ↓
Paketmanager
```

---

### Leerlaufabhängige Ausführung

LUMS kann die Ausführung von Updates aufschieben, solange ein Client als aktiv gilt.

Der aktuelle Leerlaufgrenzwert beträgt **300 Sekunden**.

Sofern unterstützt, verwendet der Agent die lokalen Sitzungs- und Leerlaufinformationen über `loginctl`.

Wenn die Leerlauferkennung nicht verfügbar ist, gibt LUMS nicht fälschlich vor, der Client sei im Leerlauf.

Diese Unterscheidung ist wichtig, denn **ein unbekannter Leerlaufstatus ist nicht dasselbe wie ein bestätigter Leerlaufstatus**.

---

### Auftragswiederherstellung

Update-Aufträge sind darauf ausgelegt, Unterbrechungen zu überstehen.

Der Server hält den persistenten Status der Aufträge und Paketpositionen vor.

Bei einer Wiederherstellung werden bereits erfolgreiche Paketoperationen nicht unnötig erneut ausgeführt.

Dadurch entsteht ein prüfpunktähnliches Ausführungsmodell für Operationen mit mehreren Paketen.

Das Ziel lautet:

> **Den Auftrag wiederherstellen, statt ihn blind vollständig neu zu starten.**

---

### Neustarterkennung

Einige Paketoperationen können einen Systemneustart erfordern.

LUMS behandelt die Neustarterkennung deshalb als Bestandteil der Verarbeitung von Update-Ergebnissen. Ein erfolgreicher Rückgabecode des Paketmanagers bedeutet nicht automatisch, dass das System bereits wieder vollständig betriebsbereit ist.

Der Client meldet die erkannte Neustartanforderung an den Server zurück.

---

### Clientauthentifizierung

Die Clientkommunikation wird über individuelle Client-Token authentifiziert.

Token sind:

- individuell zugewiesen
- erneuerbar
- serverseitig nur als SHA-256-Hashwerte gespeichert
- werden vor der Annahme von Clientmeldungen validiert

Durch eine Token-Erneuerung kann ein Administrator bisherige Zugangsdaten ungültig machen, ohne den Client neu anlegen zu müssen.

---

### Nachvollziehbarkeit

Administrative und sicherheitsrelevante Aktionen werden über das LUMS-Audit-Log-System erfasst.

Das Audit-Protokoll soll folgende Fragen beantworten:

```text
Wer?
Was?
Wann?
Welches Objekt war betroffen?
Mit welchem Ergebnis?
```

Dazu gehören sicherheitskritische Vorgänge wie authentifizierungsbezogene Aktionen, Clientverwaltung, Benutzerverwaltung und das Erstellen von Update-Aufträgen.

---

## Gestaltungsprinzip

LUMS folgt einem einfachen Grundsatz:

> **Die Linux-Updateverwaltung sichtbar, kontrolliert, wiederherstellbar und nachvollziehbar machen – ohne die darunterliegenden Linux-Werkzeuge zu verbergen.**

## Architektur

LUMS trennt Verwaltung, Ausführung und Speicherung in klar definierte Komponenten.

Der Server ist für Orchestrierung und Richtlinien zuständig.

Der Client ist für die lokale Systeminteraktion verantwortlich.

Der Paketmanager bleibt dafür zuständig, Software tatsächlich zu installieren, zu entfernen oder zu aktualisieren.

Diese Trennung ist beabsichtigt.

```text
Browser
   │
   │ HTTPS
   ▼
┌──────────────────────────────────────────┐
│               LUMS-Server                │
│                                          │
│ Weboberfläche                            │
│ Authentifizierung / Sitzungen            │
│ RBAC                                     │
│ API                                      │
│ Clientverwaltung                         │
│ Paketsuche                               │
│ Update-Auftragsverwaltung                │
│ Audit-Protokollierung                    │
│ SQLite-Persistenz                        │
└───────────────────┬──────────────────────┘
                    │
                    │ HTTPS / Client-API
                    ▼
┌──────────────────────────────────────────┐
│                LUMS-Agent                │
│                                          │
│ Authentifizierung                        │
│ Inventarmeldung                          │
│ Update-Erkennung                         │
│ Paketsuche                               │
│ Auftragsausführung                       │
│ Ergebnismeldung                          │
│ Neustarterkennung                        │
│ Leerlauferkennung                        │
└───────────────────┬──────────────────────┘
                    │
                    ▼
          ┌────────────────────┐
          │ Paketmanager       │
          │                    │
          │ APT / dpkg          │
          │ pacman              │
          └────────────────────┘
```

---

## Serverkomponenten

Der LUMS-Server stellt die zentrale Verwaltungsebene bereit.

### Webanwendung

Die Webanwendung stellt die Verwaltungsoberfläche für folgende Bereiche bereit:

- Clientverwaltung
- Softwareinventar
- Updateinformationen
- Update-Aufträge
- Paketverwaltung
- Updateverlauf
- Benutzerverwaltung
- Systemwartung

Die Oberfläche berücksichtigt die RBAC-Rolle des angemeldeten Benutzers.

Die sichtbaren Funktionen werden daher an die Berechtigungen des Benutzers angepasst. Die Autorisierung wird jedoch zusätzlich immer serverseitig durchgesetzt.

---

### API

Die API verbindet die Weboberfläche und die Linux-Clients mit der serverseitigen Anwendungslogik.

Sie verarbeitet unter anderem:

- Clientregistrierung und -verwaltung
- Clientmeldungen
- Paketsuchen
- Paketsuchergebnisse
- Update-Aufträge
- Auftragsergebnisse
- Benutzerverwaltung
- Audit-Ereignisse

API-Endpunkte validieren Eingaben, bevor zustandsverändernde Aktionen ausgeführt werden.

---

### Authentifizierung und Sitzungen

Administratoren melden sich über die LUMS-Webanwendung an.

Sitzungen werden serverseitig verwaltet und können ausdrücklich widerrufen werden.

Zu den Sicherheitsmechanismen der Authentifizierung gehören:

- Passwort-Hashing mit Argon2
- Sitzungsverwaltung
- Sitzungswiderruf
- Begrenzung der Anmeldeversuche
- CSRF-Schutz
- rollenbasierte Autorisierung

Die Clientauthentifizierung ist von der administrativen Authentifizierung getrennt.

---

### RBAC

LUMS kombiniert Rollenvorlagen mit individuellen Berechtigungen pro Benutzer. Die Vorlagen Administrator, Operator und Viewer bieten Ausgangsberechtigungen, die für jedes Konto angepasst werden können.

Die Autorisierung wird serverseitig anhand der für das Konto gespeicherten Berechtigungen durchgesetzt.

Zusätzlich blendet das Frontend Funktionen aus, die der Benutzer nicht verwenden darf.

Das bedeutet: Das Ausblenden einer Schaltfläche gilt niemals als Sicherheitsgrenze.

---

### SQLite-Persistenz

LUMS verwendet SQLite zur dauerhaften Speicherung des Anwendungszustands.

Die Datenbank speichert unter anderem:

- Benutzer
- Sitzungen
- Clients
- Client-Authentifizierungsstatus
- Softwareinventar
- verfügbare Updates
- Update-Aufträge
- Ergebnisse einzelner Paketoperationen
- Paketsuchanfragen und Suchergebnisse
- Audit-Informationen

Die Anwendung aktiviert die Durchsetzung von SQLite-Fremdschlüsseln ausdrücklich für Datenbankverbindungen.

Die aktuelle SQLite-Basiskonfiguration für den Produktivbetrieb lautet:

```text
journal_mode = wal
busy_timeout = 5000
synchronous = 2
foreign_keys = ON
```

Die aktuelle Produktivkonfiguration verwendet den WAL-Modus von SQLite.

---

## Containerarchitektur

Der LUMS-Server wird in einem gehärteten Docker-Container bereitgestellt.

Der Anwendungskontainer wird bewusst als ersetzbar behandelt.

Der persistente Anwendungszustand wird in einem dedizierten Docker-Volume gespeichert:

```text
lums-data
```

Das Root-Dateisystem des Produktivcontainers ist schreibgeschützt.

Schreibbare Speicherorte sind gezielt auf die erforderlichen Laufzeit- und persistenten Speicherpfade begrenzt.

Die Sicherheitsbasis für den Produktivbetrieb umfasst:

```text
schreibgeschütztes Root-Dateisystem
alle Linux-Capabilities entfernt
no-new-privileges
eingeschränktes /tmp
eingeschränktes /run
schreibgeschützter Secret-Mount
dediziertes persistentes Datenvolume
nicht privilegierter Anwendungsbenutzer
```

Die Anwendung ist intern unter folgender Adresse erreichbar:

```text
127.0.0.1:5050
```

Der externe HTTPS-Zugriff erfolgt über den Reverse Proxy.

---

## Persistente und ersetzbare Komponenten

LUMS trennt dauerhafte Zustände von austauschbaren Laufzeitkomponenten.

```text
Persistent
├── SQLite-Datenbank
├── Clientstatus
├── Benutzerstatus
├── Auftragsstatus
└── Auditstatus

Ersetzbar
├── Docker-Container
├── Anwendungsprozess
└── generierter Laufzeitzustand
```

Das Ersetzen des Anwendungskontainers löscht die LUMS-Datenbank daher nicht automatisch.

Diese Trennung ist für Aktualisierungen und Wiederherstellung wichtig.

---

## Clientarchitektur

Der Linux-Client besteht aus mehreren zusammenarbeitenden Komponenten.

### LUMS-Agent

Der Agent ist für die Interaktion mit dem LUMS-Server und dem lokalen Linux-System zuständig.

Aktuelle Agent-Version:

```text
1.7.0
```

Der Agent übernimmt:

- Authentifizierung
- Inventarerfassung
- Update-Erkennung
- Paketsuche
- Paketoperationen
- Ausführung von Update-Aufträgen
- Ergebnismeldung
- Neustarterkennung
- Behandlung des Leerlaufstatus
- Mitwirkung an der Auftragswiederherstellung

---

### Paketmanagerschicht

Die Paketmanagerschicht stellt eine kontrollierte Abstraktion über den nativen Linux-Paketmanager bereit.

LUMS muss den Paketmanager nicht ersetzen.

Stattdessen gilt:

```text
LUMS-Aktion
    │
    ▼
Paketmanager-Abstraktion
    │
    ├── Debian / Ubuntu → APT / dpkg
    │
    └── Arch Linux     → pacman
```

Dadurch bleibt distributionsspezifische Paketbehandlung innerhalb des Clients.

---

### Ausführungs-Watcher

Der Watcher überwacht die Ausführung von Update-Aufträgen auf dem Client.

Aktuelle Watcher-Version:

```text
1.2.1
```

Der Watcher arbeitet mit dem Agenten und dem serverseitigen Auftragsstatus zusammen.

Sein Zweck besteht darin, Ausführungssituationen zu erkennen, in denen ein Auftrag, der ausgeführt werden sollte, unbegrenzt unbearbeitet bleibt.

---

## Meldeweg

Die normale Clientkommunikation verläuft in dieser Richtung:

```text
Linux-Client
   │
   │ Inventar- / Updateinformationen
   ▼
LUMS-API
   │
   ▼
SQLite
   │
   ▼
Weboberfläche
```

Eine vom Client durchgeführte Updateprüfung erzeugt beispielsweise Informationen, die an den Server gemeldet und als aktueller Updatezustand des Clients gespeichert werden.

Der Browser fragt den Paketmanager des Clients nicht direkt ab.

---

## Ablauf der Paketsuche

Die Paketsuche folgt einem eigenen Anfrage- und Antwortablauf:

```text
Browser
  │ Suchanfrage
  ▼
LUMS-Server
  │ Paketsuchauftrag
  ▼
Linux-Client
  │ APT- / pacman-Suche
  ▼
Linux-Client
  │ Suchergebnis
  ▼
LUMS-Server
  │
  ▼
Browser
```

Der Server muss daher keinen vollständigen entfernten Paketindex für jeden Client pflegen.

Die Suche wird in der Paketverwaltungsumgebung des jeweiligen Clients ausgeführt.

---

## Ablauf der Update-Ausführung

Ein Update-Auftrag folgt grundsätzlich dieser Architektur:

```text
Browser
  │ Auftrag erstellen
  ▼
LUMS-API
  │ Anfrage validieren
  ▼
SQLite
  │ Persistenter Auftrag
  ▼
Linux-Client
  │ Aktion ausführen
  ▼
APT / dpkg / pacman
  │ Ergebnis
  ▼
Linux-Client
  │ Validiertes Ergebnis
  ▼
LUMS-API
  │
  ▼
SQLite
  │
  ▼
Browser
```

Die zentrale LUMS-Ausführungskette lautet:

> **Browser → API → SQLite → Agent → Paketmanager → Ergebnis → SQLite → Oberfläche**

---

## Atomare Auftragsübernahme

Update-Aufträge sind persistente serverseitige Objekte.

Vor der Ausführung muss der Agent einen Auftrag übernehmen, der ausgeführt werden darf.

Die Übernahme erfolgt atomar, damit derselbe ausstehende Auftrag nicht unbeabsichtigt von mehreren Ausführungspfaden übernommen wird.

Das ist besonders wichtig, wenn Timer, Wiederholungsversuche, Wiederherstellung oder mehrere clientseitige Prozesse beteiligt sind.

---

## Auftragsausführung

Der Server erstellt strukturierte Aufträge.

Der Client-Agent interpretiert die unterstützten Auftragsaktionen und führt die entsprechende lokale Operation aus.

Die unterstützten Paketaktionen sind:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Paketnamen werden validiert, bevor ein Paketauftrag erstellt wird.

Der Agent behandelt Paketnamen nicht als beliebige Shell-Fragmente.

---

## Paketverwaltungsabstraktion

Paketoperationen werden bewusst hinter einer Paketmanager-Abstraktion implementiert.

Dadurch bleibt das übergeordnete LUMS-Auftragsmodell unabhängig von distributionsspezifischen Befehlen.

Beispiel:

```text
INSTALL_PACKAGE
      │
      ├── Debian / Ubuntu → APT
      │
      └── Arch Linux     → pacman
```

Dasselbe Prinzip gilt für das Entfernen und Aktualisieren von Paketen.

---

## Debian / Ubuntu

Auf Debian-basierten Systemen verwendet LUMS die nativen APT-/dpkg-Werkzeuge.

Typische Aufgaben sind:

- Paketsuche
- Abruf von Paketmetadaten
- Paketinstallation
- Paketentfernung
- Paketaktualisierungen
- Systemaktualisierungen
- Update-Erkennung

Der LUMS-Agent ersetzt APT nicht.

Er stellt eine kontrollierte Orchestrierung darum bereit.

---

## Arch Linux

Auf Arch-Linux-Systemen verwendet LUMS den nativen Paketmanager pacman.

Typische Aufgaben sind:

- Paketsuche
- Abruf von Paketmetadaten
- Paketinstallation
- Paketentfernung
- Paketaktualisierungen
- Systemaktualisierungen
- Update-Erkennung

Distributionsspezifisches Verhalten bleibt innerhalb der Paketmanagerschicht.

---

## Paketsuche

Die Paketsuche ist vom Inventar der installierten Software getrennt.

Diese Unterscheidung ist wichtig:

```text
Installierte Software
       │
       └── Was ist bereits installiert?

Paketsuche in der Paketverwaltung
       │
       └── Welche Pakete findet der Client aktuell?
```

Suchergebnisse können Informationen enthalten wie:

- Paketname
- Version
- Beschreibung
- Repository-Informationen, sofern verfügbar

Die Suchergebnisse werden an den LUMS-Server zurückgegeben und in der Paketverwaltungsoberfläche angezeigt.

---

## Berechtigungen der Paketverwaltung

Paketverwaltung ist ein privilegierter Vorgang.

Das aktuelle Berechtigungsmodell lautet:

```text
Administrator → erlaubt
Operator      → erlaubt
Viewer        → nicht erlaubt
```

Ein Viewer kann weiterhin installierte Software einsehen.

Die Paketverwaltungsoberfläche ist für Viewer ausgeblendet. Die entsprechenden serverseitigen Endpunkte für Änderungen erzwingen die Berechtigungen unabhängig davon.

---

## Verarbeitung von Update-Ergebnissen

LUMS behandelt das Ergebnis einer Update-Operation als strukturierten Zustand und nicht lediglich als rohe Befehlsausgabe.

Relevante Informationen können umfassen:

- Erfolg oder Fehlschlag
- Ergebnis auf Paketebene
- Ausführungsstatus
- Fehlerinformationen
- erforderlicher Neustart
- Abschlusszeitpunkte

Dadurch kann der Server einen aussagekräftigen Updateverlauf führen.

---

## Neustarterkennung

Nach Paketoperationen prüft der Client, ob ein Neustart erforderlich ist.

Das Ergebnis wird als Bestandteil des Auftragsergebnisses an den Server gemeldet.

Eine erforderliche Neustartaktion bleibt so mit der Update-Operation verknüpft, statt in einer clientseitigen Terminalsitzung verloren zu gehen.

---

## Grenze der Clientauthentifizierung

Die Client-API verwendet einen anderen Authentifizierungsmechanismus als administrative Websitzungen.

```text
Administrativer Benutzer
       │
       ▼
Webauthentifizierung
       │
       ▼
   LUMS-Server

Linux-Client
       │
       ▼
   Client-Token
       │
       ▼
   LUMS-Server
```

Diese Trennung verhindert, dass administrative Browsersitzungen und Client-Zugangsdaten als austauschbare Authentifizierungsmechanismen verwendet werden.

---

## Audit-Trail

Sicherheitsrelevante und administrative Aktionen werden vom serverseitigen Auditsystem erfasst.

Der Audit-Trail ergänzt die normalen Anwendungsprotokolle.

Protokolle beantworten Fragen zum Anwendungsverhalten.

Audit-Protokolle halten zusätzlich wichtige administrative Aktionen und deren Kontext fest.

Das ist hilfreich, wenn Änderungen an Clients, Benutzern, Authentifizierungszuständen oder Update-Aufträgen untersucht werden müssen.

---

## Betriebsprinzip

LUMS trennt bewusst:

```text
Verwaltung
    │
    ▼
Richtlinien / Autorisierung
    │
    ▼
Auftrag
    │
    ▼
Clientausführung
    │
    ▼
Nativer Paketmanager
```

Jede Ebene hat eine klar definierte Verantwortung.

Der Server verwaltet.

Der Agent führt aus.

Der Paketmanager nimmt die eigentliche Systemänderung vor.

Das Ergebnis läuft über dieselbe kontrollierte Kette zurück.

## Rollenbasierte Zugriffskontrolle

LUMS verwendet drei administrative Rollen:

```text
Administrator
Operator
Viewer
```

Die Autorisierung wird serverseitig durchgesetzt.

Das Frontend passt zusätzlich die sichtbare Oberfläche an die Berechtigungen des Benutzers an. Die Sichtbarkeit im Frontend gilt jedoch niemals als Sicherheitsgrenze.

### Administrator

Administratoren dürfen:

- Clients anzeigen
- installierte Software anzeigen
- verfügbare Updates anzeigen
- Update-Aufträge erstellen und ausführen
- den Updateverlauf einsehen
- die Paketverwaltung verwenden
- Systemwartung durchführen
- Clients erstellen und deaktivieren
- Client-Token erneuern
- Benutzer erstellen und verwalten
- Rollen und Benutzerzugriffe verwalten

### Operator

Operatoren dürfen:

- Clients anzeigen
- installierte Software anzeigen
- verfügbare Updates anzeigen
- Update-Aufträge erstellen und ausführen
- den Updateverlauf einsehen
- die Paketverwaltung verwenden
- Systemwartung durchführen

Operatoren dürfen nicht:

- Benutzer verwalten
- Rollen administrieren
- Clients erstellen oder deaktivieren
- Client-Token erneuern

### Viewer

Viewer haben Lesezugriff auf:

- Clients
- installierte Software

Folgende Funktionen stehen Viewern nicht zur Verfügung:

- Verwaltung verfügbarer Updates
- Update-Aufträge
- Updateverlauf
- Paketverwaltung
- Systemwartung
- andere zustandsverändernde administrative Aktionen

Der Server setzt diese Einschränkungen unabhängig davon durch.

---

## Benutzerverwaltung

LUMS stellt Benutzern mit der Berechtigung `users.manage` eine Benutzerverwaltung bereit.

Berechtigte Benutzer können Konten anhand einer Rollenvorlage erstellen und anschließend einzelne Berechtigungen zuweisen oder die Vorlage ausdrücklich anwenden. Neue Konten starten ohne Berechtigungen; nach der Erstellung wird der Berechtigungseditor geöffnet. Benutzerverwalter können außerdem private administrative Notizen speichern, die für den Kontoinhaber nicht sichtbar sind.

Administratoren mit `backups.manage` können validierte Datenbank-Backups im Format `.db` oder `.db.gz` in einem serverseitig konfigurierten Verzeichnis erstellen und einen sicheren Unterordner innerhalb dieses eingebundenen Speicherorts auswählen. Hinweise zur Docker-Speicherkonfiguration und Wiederherstellung stehen in [`administration.md`](Administration und Backups.md) und in der integrierten Markdown-Anleitung zur Wiederherstellung.

Benutzerpasswörter werden mit Argon2 gehasht und weder im Klartext noch mit umkehrbarer Verschlüsselung gespeichert.

Benutzerverwaltungsaktionen sind geschützt durch:

- Authentifizierung
- berechtigungsbasierte Autorisierung
- CSRF-Schutz
- Eingabevalidierung
- Prüfung auf doppelte Benutzernamen
- Audit-Protokollierung

Die Benutzerverwaltungsoberfläche wird ohne `users.manage` nicht angezeigt.

---

## Sitzungssicherheit

Die administrative Authentifizierung verwendet eine serverseitige Sitzungsverwaltung.

Zu den Sicherheitsmaßnahmen gehören:

- authentifizierter Sitzungsstatus
- Sitzungswiderruf
- CSRF-Schutz bei zustandsverändernden Anfragen
- Begrenzung der Anmeldeversuche
- Durchsetzung deaktivierter Konten
- Rollenprüfungen

Beim Widerruf einer Sitzung wird der zugehörige authentifizierte Zustand ungültig gemacht, anstatt lediglich die Benutzeroberfläche auszublenden.

---

## Begrenzung von Anmeldeversuchen

Wiederholte fehlgeschlagene Anmeldeversuche unterliegen einer progressiven Begrenzung.

Die aktuellen Schwellenwerte sind:

```text
5 Versuche   → 30 Sekunden
6 Versuche   → 60 Sekunden
7 Versuche   → 120 Sekunden
8+ Versuche  → 300 Sekunden
```

Der zugehörige Zustand wird in SQLite gespeichert.

Eine erfolgreiche Anmeldung setzt den entsprechenden Fehlerstatus zurück.

Dadurch kann der Schutz nicht einfach durch einen Neustart der Anwendung umgangen werden.

---

## Sicherheit der Client-Token

Jeder registrierte Client besitzt ein eigenes Authentifizierungs-Token.

Der Server speichert das Token als SHA-256-Hashwert.

Das ursprüngliche Token wird für die normale serverseitige Prüfung nicht benötigt.

Durch eine Token-Erneuerung kann ein Administrator vorhandene Zugangsdaten ungültig machen und einen Ersatz ausstellen.

Der Lebenszyklus ist damit klar definiert:

```text
Erstellen
   │
   ▼
Verwenden
   │
   ▼
Erneuern
   │
   ▼
Altes Token ungültig
```

---

## API-Sicherheit

LUMS validiert API-Eingaben, bevor zustandsverändernde Aktionen ausgeführt werden.

Zu den Sicherheitsmaßnahmen gehören:

- Authentifizierung
- Autorisierung anhand der Benutzerberechtigungen
- CSRF-Schutz, wo anwendbar
- Eingabevalidierung
- Validierung von Paketnamen
- strukturierte Auftragsaktionen
- parametrisierte Datenbankabfragen
- kontrollierte Fehlerbehandlung

Die Anwendung verwendet von Benutzern übermittelte Paketnamen nicht als uneingeschränkte Shell-Befehle.

---

## Schutz vor SQL-Injection

Datenbankoperationen verwenden parametrisierte SQL-Anweisungen.

Von Benutzern kontrollierte Werte werden nicht direkt an SQL-Abfragen angehängt.

Dies betrifft Bereiche wie:

- Authentifizierung
- Clientverwaltung
- Benutzerverwaltung
- Paketsuchen
- Update-Aufträge
- Audit-Daten
- Ergebnismeldungen

Ziel ist es, Datenwerte und SQL-Anweisungen getrennt zu halten.

---

## SQLite-Sicherheitsbasis

Die aktuelle SQLite-Konfiguration für den Produktivbetrieb lautet:

```text
journal_mode = wal
busy_timeout = 5000
synchronous = 2
foreign_keys = ON
```

Die Anwendung aktiviert die Fremdschlüsselprüfung für Datenbankverbindungen ausdrücklich.

Die aktuelle Konfiguration verwendet den WAL-Modus.

Die Datenbank befindet sich im persistenten Docker-Volume und nicht im Dateisystem des ersetzbaren Anwendungskontainers.

---

## Auftragswiederherstellung und Prüfpunkte

LUMS behandelt Update-Aufträge als persistente Zustandsautomaten.

Ein Auftrag mit mehreren Paketen kann mehrere einzelne Paketoperationen enthalten.

Jede Paketposition kann einen eigenen Ergebnisstatus erreichen.

Nach einer Unterbrechung kann die Wiederherstellung unterscheiden zwischen:

```text
bereits erfolgreich
       │
       └── nicht unnötig wiederholen

nicht abgeschlossen
       │
       └── für die Wiederherstellung geeignet
```

Dadurch sinkt das Risiko, nach einer Unterbrechung bereits abgeschlossene Paketoperationen blind erneut auszuführen.

---

## Kontrollierte Update-Ausführung

LUMS begrenzt bewusst die Aktionen, die über die Update-Auftrags-API angefordert werden können.

Unterstützte Aktionen:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Der Server validiert die Aktion und die zugehörigen Paketinformationen, bevor er den Auftrag erstellt.

Der Agent ordnet die strukturierte Aktion anschließend der passenden Paketmanager-Operation zu.

So wird verhindert, dass das Updatesystem zu einem allgemeinen Mechanismus für die Ausführung entfernter Befehle wird.

---

## Paketoperationen

Paketoperationen werden über den nativen Paketmanager des Clients ausgeführt.

### Installation

Ein validierter Paketname wird zur Installation an die Paketmanager-Abstraktion übergeben.

### Entfernung

Ein validierter Paketname wird zur Entfernung an die Paketmanager-Abstraktion übergeben.

### Paketaktualisierung

Ein bestimmtes Paket kann aktualisiert werden, wenn der Client es als verfügbares Update meldet.

### Systemaktualisierung

Die Systemaktualisierung übergibt den Aktualisierungsvorgang an den nativen Paketmanager.

Alle Operationen geben strukturierte Ergebnisse an den LUMS-Server zurück.

---

## Sicherheit des Paketmanagers

LUMS behandelt den Paketmanager als privilegierte lokale Komponente.

Der Agent versucht daher nicht, das Verhalten des Paketmanagers selbst nachzubilden.

Stattdessen:

1. validiert er die angeforderte Operation
2. wählt die passende Paketmanager-Implementierung aus
3. führt die kontrollierte Operation aus
4. erfasst das Ergebnis
5. meldet das Ergebnis an den Server

Distributionsspezifisches Verhalten bleibt innerhalb der Paketmanagerschicht isoliert.

---

## Neustartbehandlung

Einige Paketoperationen können einen Neustart erfordern.

LUMS speichert Neustartanforderungen als Bestandteil der Update-Auftragsergebnisse.

So können Administratoren unterscheiden zwischen:

```text
Update abgeschlossen
```

und:

```text
Update abgeschlossen
Neustart erforderlich
```

Die Neustartanforderung ist damit Bestandteil des Betriebszustands und keine unabhängige Benachrichtigung.

---

## Audit-Protokollierung

LUMS führt einen Anwendungs-Audit-Trail für wichtige administrative und sicherheitsrelevante Aktionen.

Beispiele sind:

- authentifizierungsbezogene Ereignisse
- Clientverwaltung
- Token-Operationen
- Benutzerverwaltung
- Erstellung von Update-Aufträgen
- sicherheitskritische Zustandsänderungen

Die Audit-Protokollierung ist von der gewöhnlichen Diagnoseprotokollierung getrennt.

Diagnoseprotokolle helfen bei der Fehlersuche.

Audit-Einträge liefern einen administrativen Verlauf relevanter Aktionen.

---

## Sicherheitshärtung

Die aktuelle Bereitstellung umfasst mehrere Härtungsebenen.

### Container-Härtung

Der Produktivcontainer verwendet:

- Ausführung als nicht privilegierter Benutzer
- schreibgeschütztes Root-Dateisystem
- entfernte Linux-Capabilities
- `no-new-privileges`
- eingeschränkte temporäre Dateisysteme
- schreibgeschützten Secret-Mount
- dediziertes persistentes Datenvolume

### Netzwerkhärtung

Der Anwendungskontainer ist auf dem Host an die Loopback-Adresse gebunden:

```text
127.0.0.1:5050
```

Der Anwendungsport wird daher nicht direkt als LAN-Dienst bereitgestellt.

Der externe Zugriff erfolgt über den HTTPS-Reverse-Proxy.

Die Firewall gibt den internen Anwendungsport nicht frei.

### Transportsicherheit

Der administrative Zugriff erfolgt über HTTPS.

Der Reverse Proxy übernimmt die externe TLS-Terminierung.

HTTP-Anfragen werden auf HTTPS umgeleitet.

### Geheimnisse und Konfiguration

Sensible Laufzeit-Zugangsdaten werden außerhalb des Quellcodeverzeichnisses gehalten.

Das Produktionsgeheimnis wird als schreibgeschützte Secret-Datei in den Container eingebunden.

Regeln im Repository und im Docker-Build-Kontext verhindern, dass übliche Backup-, Geheimnis-, Datenbank- und Zertifikatsdateien unbeabsichtigt in den Image-Build-Kontext gelangen.

### Abhängigkeits- und Buildsicherheit

Die Python-Abhängigkeiten für den Produktivbetrieb sind fest versioniert.

Das Python-Basisimage für den Produktivbetrieb ist per Digest festgelegt.

Der Docker-Build-Kontext wird durch `.dockerignore` eingeschränkt.

Diese Maßnahmen verbessern die Reproduzierbarkeit des Builds und verringern das Risiko, versehentlich sensible Dateien einzuschließen.

---

## Status der Sicherheitsprüfung

Die Sicherheitsprüfung von LUMS hat folgende Bereiche abgedeckt:

- Durchsetzung von SQLite-Fremdschlüsseln
- SQLite-Laufzeitkonfiguration
- Update-Timeouts und Prozessbehandlung
- Begrenzung von Anmeldeversuchen
- API-Eingabevalidierung
- Sitzungswiderruf
- Erneuerung von Client-Token
- Offline- und IP-Behandlung
- Auftragswiederherstellung und Prüfpunkte
- Robustheit von APT
- Neustarterkennung unter Arch Linux
- Validierung von Einheiten- und API-Ergebnissen
- Simulationstests
- kontinuierliche Integration
- Anwendungs- und Audit-Protokollierung
- Versionierung und Release-Verfahren
- RBAC
- Sitzungs- und CSRF-Sicherheit
- Sicherheit von Zugangsdaten
- Abhängigkeits- und Buildsicherheit
- Docker- und Container-Härtung
- Schutz von Geheimnissen und Build-Kontext
- HTTP- und Transportsicherheit
- Dateisystem- und Laufzeitberechtigungen
- Netzwerkexposition
- Sauberkeit der Repository-Artefakte

Die abschließende Dokumentationsprüfung wird im Rahmen des Release-Readiness-Prozesses separat durchgeführt.

---

## Tests und CI

LUMS enthält automatisierte Tests für das grundlegende Anwendungsverhalten und Sicherheitskontrollen.

Führe die vollständige Testsuite im Stammverzeichnis des Repositorys aus:

```bash
./.venv-test/bin/pytest -q
```

Die Anzahl der Tests ändert sich im Laufe der Entwicklung. Entscheidend ist, dass die vollständige Testsuite ohne Fehler erfolgreich durchläuft. Sie umfasst unter anderem Tests für:

- Authentifizierung
- RBAC
- Clientverwaltung
- Benutzerverwaltung
- Paketsuche
- Update-Aufträge
- Validierung von Auftragsergebnissen
- Sicherheitsverhalten
- API-Verhalten

Die kontinuierliche Integration führt die automatisierte Testsuite aus, bevor Änderungen als bereit betrachtet werden.

Ein erfolgreicher Testlauf ist erforderlich, aber Tests sind nur ein Teil des Release-Prozesses.

Zusätzlich erforderlich sind:

```text
Implementierung
      ↓
Sicherheitsprüfung
      ↓
Dokumentationsprüfung
      ↓
Vollständige Testsuite
      ↓
CI
      ↓
Version
      ↓
Git-Tag
      ↓
GitHub-Release
```

---

## Entwicklungsstatus

LUMS befindet sich in aktiver Entwicklung.

Die zentrale Verwaltungsarchitektur, das clientseitige Ausführungsmodell, die Paketverwaltung, RBAC, Sicherheitshärtung und Wiederherstellungsmechanismen sind implementiert.

Das Projekt gilt nicht allein deshalb als fertiges Release, weil die Anwendung funktioniert.

Zur Release-Reife gehört auch, dass die begleitende Dokumentation und die Betriebsverfahren das aktuelle System korrekt beschreiben.

Deshalb wird die Konsistenz der Dokumentation als Teil des Entwicklungsprozesses und nicht als nachträgliche Aufgabe behandelt.

## Unterstützte Systeme

LUMS ist für die Verwaltung von Linux-Systemen mit unterstützten nativen Paketmanagern ausgelegt.

### Debian / Ubuntu

Unterstützter Paketverwaltungs-Stack:

```text
APT
dpkg
```

Der Client verwendet die nativen Debian-Paketwerkzeuge für:

- Paketinventar
- Update-Erkennung
- Paketsuche
- Paketinstallation
- Paketentfernung
- Paketaktualisierungen
- Systemaktualisierungen

### Arch Linux

Unterstützter Paketverwaltungs-Stack:

```text
pacman
```

Der Client verwendet die nativen Arch-Paketwerkzeuge für:

- Paketinventar
- Update-Erkennung
- Paketsuche
- Paketinstallation
- Paketentfernung
- Paketaktualisierungen
- Systemaktualisierungen

---

## Anforderungen an Clients

Ein verwalteter Linux-Client benötigt:

- eine unterstützte Linux-Distribution
- den LUMS-Agent
- Netzwerkverbindung zum LUMS-Server
- ein registriertes Client-Token
- einen funktionierenden nativen Paketmanager
- systemd für timer- und servicebasierte Ausführungskomponenten

Der Client benötigt keinen direkten Zugriff des LUMS-Servers auf seine Paketdatenbank.

Der Client führt lokale Paketoperationen aus und meldet die Ergebnisse an den Server.

---

## Technologie-Stack

### Server

- Python
- Flask
- Gunicorn
- SQLite
- HTML
- CSS
- JavaScript
- Nginx
- Docker

### Authentifizierung und Sicherheit

- Argon2-Passwort-Hashing
- serverseitige Sitzungen
- CSRF-Schutz
- Rollenvorlagen mit individuellen Benutzerberechtigungen
- SHA-256-Hashwerte für Client-Token
- HTTPS
- Audit-Protokollierung

### Client

- Python
- systemd
- APT / dpkg
- pacman
- `loginctl`, sofern Informationen zum Leerlaufstatus verfügbar sind

---

## Projektstruktur

Das Repository ist in Server-, Client-, Frontend- und Testkomponenten unterteilt.

Eine vereinfachte Struktur sieht so aus:

```text
LUMS/
├── agent/
│   ├── agent.py
│   └── package_manager.py
│
├── server/
│   ├── app.py
│   ├── migrations/
│   ├── static/
│   ├── templates/
│   └── ...
│
├── tests/
│   ├── test_rbac.py
│   ├── test_package_search.py
│   ├── test_job_result.py
│   └── ...
│
├── Dockerfile
├── docker-entrypoint.sh
├── .dockerignore
├── .gitignore
└── Dokumentation
```

Die genaue Repository-Struktur kann sich während der Entwicklung von LUMS verändern.

Die architektonische Trennung zwischen Server, Agent, Paketmanager-Abstraktion, Frontend und Tests ist beabsichtigt.

---

## Serveranwendung

Die Flask-Anwendung stellt die zentrale LUMS-API und Weboberfläche bereit.

Zu ihren Aufgaben gehören:

- Authentifizierung
- Autorisierung
- Sitzungsverwaltung
- Clientverwaltung
- Benutzerverwaltung
- Softwareinventar
- Updateinventar
- Paketsuche
- Update-Aufträge
- Verarbeitung von Auftragsergebnissen
- Audit-Protokollierung
- Datenbankpersistenz

Die Anwendung wird innerhalb des Containers von Gunicorn bereitgestellt.

Nginx stellt den externen HTTPS-Zugang bereit.

---

## Agent

Der LUMS-Agent wird direkt auf verwalteten Linux-Clients installiert.

Aktuelle Agent-Version:

```text
1.7.0
```

Der Agent übernimmt den clientseitigen Teil der LUMS-Ausführungskette.

Zu seinen Aufgaben gehören:

- Clientstatus melden
- installierte Software erfassen
- verfügbare Updates erkennen
- Pakete suchen
- Paketoperationen ausführen
- Auftragsergebnisse melden
- erforderliche Neustarts erkennen
- Leerlaufstatus behandeln
- an der Auftragswiederherstellung mitwirken

Der Agent stellt keine uneingeschränkte Remote-Shell bereit.

---

## Paketmanagerschicht

Die Paketmanager-Implementierung kapselt distributionsspezifisches Verhalten gegenüber dem restlichen Agenten.

Konzeptionell:

```text
Agent
  │
  ▼
Paketmanager-Schnittstelle
  │
  ├── Debian / Ubuntu
  │      └── APT / dpkg
  │
  └── Arch Linux
         └── pacman
```

So kann das übergeordnete Update-Auftragssystem mit strukturierten Operationen arbeiten, ohne jeden distributionsspezifischen Befehl kennen zu müssen.

---

## Watcher

Der LUMS-Ausführungs-Watcher überwacht Aufträge, die auf dem Client ausgeführt werden sollen.

Aktuelle Watcher-Version:

```text
1.2.1
```

Der Watcher arbeitet mit dem Agenten und dem serverseitigen Auftragsstatus zusammen.

Diese Architektur hilft LUMS, Situationen zu erkennen, in denen ein Auftrag aussteht oder anderweitig Aufmerksamkeit erfordert.

---

## systemd-Integration

Der Client verwendet systemd für geplante und kontrollierte Ausführung.

Zu den relevanten Komponenten gehören Service- und Timer-Units für:

- Clientmeldungen
- Update-Erkennung
- Auftragsausführung und Überwachung

Dadurch wird eine vorhersehbare Ausführung ermöglicht, ohne für jeden periodischen Vorgang einen dauerhaft laufenden Vordergrundprozess zu benötigen.

Der Client-Agent kann während der Installation und Fehlersuche auch manuell ausgeführt werden.

---

## Leerlaufabhängige Ausführung

Die leerlaufabhängige Ausführung soll Störungen für aktive Benutzer verringern.

Der aktuelle Leerlaufgrenzwert beträgt:

```text
300 Sekunden
```

Der Client bestimmt den Leerlaufstatus anhand der verfügbaren lokalen Sitzungsinformationen.

Sofern unterstützt, wird `loginctl` verwendet.

Der Agent unterscheidet zwischen:

```text
Leerlauf bestätigt
Aktiv
Leerlaufstatus nicht verfügbar
```

Ein nicht verfügbarer Leerlaufstatus wird nicht stillschweigend als Leerlauf interpretiert.

Dadurch bleibt die Ausführungsentscheidung explizit und nachvollziehbar.

---

## Lebenszyklus eines Update-Auftrags

Der vollständige Lebenszyklus eines Update-Auftrags lässt sich so darstellen:

```text
Erstellen
   │
   ▼
Validieren
   │
   ▼
Speichern
   │
   ▼
Übernehmen
   │
   ▼
Ausführen
   │
   ├──────────────► SUCCESS
   │
   ├──────────────► FAILED
   │
   └──────────────► RECOVERY
                          │
                          ▼
                       Ausführen
```

Ein Auftrag wird vor seiner Ausführung gespeichert.

Dadurch behält der Server den beabsichtigten Vorgang im Blick, selbst wenn der Client oder die Anwendung unterbrochen wird.

---

## Auftragstypen

LUMS unterstützt derzeit strukturierte Update-Aktionen wie:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Diese Aktionen sind bewusst begrenzt.

LUMS ist ein Updateverwaltungssystem und kein universelles Framework zur Ausführung entfernter Befehle.

---

## Auftragsstatus auf Paketebene

Aufträge mit mehreren Paketen können den Fortschritt für jedes Paket einzeln verfolgen.

Beispiel:

```text
Auftrag #42

paket-a → SUCCESS
paket-b → SUCCESS
paket-c → FAILED
paket-d → PENDING
```

Die Wiederherstellung kann dadurch auf die unvollständigen Teile eines Auftrags beschränkt werden, anstatt erfolgreiche Paketoperationen blind zu wiederholen.

---

## Auftragswiederherstellung

Die Wiederherstellung basiert auf persistenten Prüfpunkten.

Der Server verwaltet den Auftragsstatus.

Der Client meldet Ergebnisse auf Paketebene.

Wenn die Ausführung unterbrochen wird, kann der Server feststellen, welche Arbeit bereits abgeschlossen ist und welche noch wiederhergestellt werden kann.

Das beabsichtigte Wiederherstellungsprinzip lautet:

> **Vom bekannten Zustand aus fortsetzen, statt anzunehmen, dass noch nichts passiert ist.**

---

## Ergebnisvalidierung

Clientseitige Auftragsergebnisse werden validiert, bevor sie in den persistenten Serverzustand übernommen werden.

Das schützt den Auftragsstatus vor fehlerhaften oder unvollständigen Ergebnismeldungen.

Die Validierung umfasst relevante Felder wie:

- Auftragskennung
- Ausführungsstatus
- Paket-Ergebnisdaten
- Fehlerinformationen
- Neustartinformationen

Die Ergebnisverarbeitung bildet damit eine weitere Grenze zwischen einem authentifizierten Client und dem persistenten Serverzustand.

---

## Benutzerverwaltung

Die Benutzerverwaltung erfordert die Berechtigung `users.manage`.

Berechtigte Benutzer können Konten anhand einer Rollenvorlage erstellen und die einzelnen Berechtigungen des jeweiligen Kontos anpassen.

Die aktuellen Rollen sind:

```text
Administrator
Operator
Viewer
```

Benutzerverwaltungsaktionen werden authentifiziert, auf Berechtigungen geprüft, validiert, soweit anwendbar gegen CSRF geschützt und im Audit-Trail erfasst.

---

## Clientverwaltung

Administratoren können registrierte Clients verwalten.

Die Clientverwaltung umfasst:

- Registrierung
- Deaktivierung
- Erneuerung von Token
- Prüfung des Clientstatus

Jeder registrierte Client besitzt eine unabhängige Authentifizierung.

Durch die Deaktivierung eines Clients wird dessen normale authentifizierte Kommunikation mit dem Server unterbunden.

---

## Updateverlauf

LUMS speichert den Status von Update-Aufträgen dauerhaft, damit abgeschlossene und fehlgeschlagene Operationen auch nach ihrer Ausführung sichtbar bleiben.

Berechtigte Benutzer können abhängig von ihrer Rolle den Verlauf von Update-Operationen einsehen.

Der Verlauf soll den betrieblichen Kontext liefern und nicht nur das jeweils neueste Paketinventar anzeigen.

---

## Nachvollziehbarkeit

LUMS führt zwei verwandte, aber unterschiedliche Arten betrieblicher Informationen:

### Anwendungsprotokolle

Sie dienen hauptsächlich der:

- Diagnose
- Fehleranalyse
- Beobachtung des Laufzeitverhaltens
- Fehlerbehebung

### Audit-Protokolle

Sie dienen hauptsächlich der Erfassung von:

- administrativen Aktionen
- sicherheitsrelevanten Ereignissen
- Änderungen wichtiger Zustände
- Verantwortlichkeit und Nachvollziehbarkeit

Die Trennung dieser Konzepte erleichtert sowohl die Fehlersuche als auch die administrative Prüfung.

---

## Teststrategie

Die LUMS-Testsuite deckt mehrere Anwendungsebenen ab.

### Authentifizierung

Tests prüfen Authentifizierungsverhalten, Sitzungsverwaltung und Sicherheitsmechanismen.

### RBAC

Tests prüfen, dass:

- Administratoren administrative Aktionen durchführen können
- Operatoren die ihnen erlaubten Verwaltungsfunktionen erhalten
- Viewer auf schreibgeschützten Zugriff beschränkt bleiben

### Paketverwaltung

Tests decken das Verhalten der Paketsuche und die API-Verarbeitung im Zusammenhang mit der Paketverwaltung ab.

### Update-Aufträge

Tests prüfen:

- Auftragserstellung
- Validierung
- Zustandsübergänge
- Ergebnisverarbeitung
- Wiederherstellungsverhalten

### Sicherheit

Tests prüfen sicherheitskritisches Anwendungsverhalten und Regressionen.

### Vollständige Testsuite

Führe die vollständige Testsuite im Stammverzeichnis des Repositorys aus:

```bash
./.venv-test/bin/pytest -q
```

Die Anzahl der Tests ändert sich mit der Weiterentwicklung des Projekts. Maßgeblich ist das Ergebnis des Befehls und nicht eine festgelegte Zahl in diesem Dokument.

---

## Kontinuierliche Integration

Das Projekt verwendet kontinuierliche Integration, um automatisierte Prüfungen für Änderungen auszuführen.

Die CI-Pipeline hilft dabei, Regressionen zu erkennen, bevor Änderungen als releasebereit gelten.

Der Entwicklungsablauf lautet daher:

```text
Änderung
   ↓
Test
   ↓
Sicherheitsprüfung
   ↓
Dokumentationsprüfung
   ↓
CI
   ↓
Release-Vorbereitung
```

Ein erfolgreicher CI-Lauf ersetzt keine manuelle Sicherheits- oder Dokumentationsprüfung.

---

## Dokumentation

LUMS unterhält separate Dokumentation für unterschiedliche betriebliche Aufgaben.

### `README.md`

Projektübersicht, Architektur, Funktionen, Sicherheitsbasis, Entwicklungsstatus und Projektausrichtung.

### `install.md`

Installation, Bereitstellung, Clientkonfiguration, Validierung, Aktualisierung und Entfernung.

### `administration.md`

Regelmäßige Administration, Wartung, Backups, Aktualisierungen, Betriebsverfahren und Notfalladministration.

### `security.md`

Sicherheitsarchitektur, Sicherheitskontrollen, Prüfergebnisse, Härtung und Informationen zur Release-Sicherheit.

### `troubleshooting.md`

Diagnoseverfahren für Server, Clients, Aufträge, Paketverwaltung, Authentifizierung, Datenbank, Container und Netzwerkprobleme.

### `LUMS_Optional_Theme_System.md`

Architektur und Wartung optionaler LUMS-Frontend-Themes.

Die Dokumentation ist nach Zuständigkeiten getrennt, damit Betriebsanweisungen nicht mit Sicherheitsdesign oder visueller Anpassung vermischt werden.

---

## Dokumentationsprinzip

Dokumentation wird als Bestandteil des Systems behandelt.

Eine Funktion gilt nicht als vollständig, wenn der Code funktioniert, die Dokumentation aber eine ältere Architektur beschreibt.

Das angestrebte Verhältnis lautet:

```text
Implementierung
      │
      ├── Tests
      ├── Sicherheitsprüfung
      └── Dokumentation
               │
               ▼
          Releasebereit
```

Das ist besonders wichtig für sicherheitskritische Bereitstellungs- und Administrationsverfahren.

## Aktueller Status

LUMS ist eine aktiv entwickelte Plattform zur Linux-Updateverwaltung.

Die aktuelle Implementierung umfasst:

- zentrale Clientverwaltung
- Softwareinventar
- Update-Erkennung
- Paketsuche
- Paketinstallation und -entfernung
- paketbezogene Aktualisierungen
- Systemaktualisierungen
- persistente Update-Aufträge
- Auftragsstatus auf Paketebene
- Auftragswiederherstellung
- Neustarterkennung
- leerlaufabhängige Ausführung
- Client-Token-Authentifizierung
- Erneuerung von Token
- administrative Authentifizierung
- rollenbasierte Zugriffskontrolle
- Benutzerverwaltung
- Audit-Protokollierung
- Container-Härtung
- HTTPS-Transport
- automatisierte Tests
- kontinuierliche Integration

Das Projekt befindet sich derzeit in der abschließenden Dokumentations- und Release-Readiness-Phase.

---

## Sicherheitsstatus

Die wesentlichen Bereiche der Sicherheitsprüfung wurden implementiert und überprüft.

Die aktuelle Sicherheitsbasis umfasst:

```text
Authentifizierung
   ├── Argon2-Passwort-Hashing
   ├── Sitzungsverwaltung
   ├── Sitzungswiderruf
   └── Begrenzung von Anmeldeversuchen

Autorisierung
   ├── Administrator
   ├── Operator
   └── Viewer

Clientsicherheit
   ├── individuelle Client-Token
   ├── SHA-256-Token-Hashwerte
   └── Token-Erneuerung

API-Sicherheit
   ├── Eingabevalidierung
   ├── CSRF-Schutz
   ├── RBAC-Durchsetzung
   └── parametrisierte SQL-Abfragen

Laufzeitsicherheit
   ├── nicht privilegierter Container
   ├── schreibgeschütztes Root-Dateisystem
   ├── entfernte Capabilities
   ├── no-new-privileges
   ├── eingeschränkte temporäre Dateisysteme
   └── geschützter Secret-Mount

Netzwerksicherheit
   ├── HTTPS
   ├── Reverse Proxy
   ├── Bindung der Anwendung an Loopback
   └── Firewall-Beschränkungen
```

Sicherheit wird als fortlaufende Entwicklungsaufgabe behandelt und nicht als einmalige Checkliste.

---

## Release-Status

LUMS beansprucht derzeit keine stabile Produktionsrelease-Version.

Aktuell gibt es:

- keine endgültige semantische Version
- keinen stabilen Release-Tag
- kein GitHub-Release

Das Projekt folgt bewusst dieser Release-Reihenfolge:

```text
Implementierung
      ↓
Sicherheitsprüfung
      ↓
Dokumentationsprüfung
      ↓
Vollständige Testsuite
      ↓
CI
      ↓
Versionszuweisung
      ↓
Git-Tag
      ↓
GitHub-Release
```

Das erste offizielle Release sollte erst erstellt werden, wenn die aktuelle Implementierung, Sicherheitsprüfung, Dokumentation und Regressionstests als abgeschlossen gelten.

---

## Roadmap

Die Roadmap konzentriert sich bewusst auf Stabilität und Wartbarkeit, statt neue Funktionen hinzuzufügen, bevor die bestehende Grundlage abgeschlossen ist.

### Aktuelle Phase

- vollständige Dokumentationsprüfung
- verbleibende Dokumentationswidersprüche beseitigen
- Dokumentationsaudit abschließen
- abschließenden vollständigen Testlauf durchführen
- CI überprüfen
- Release-Version vorbereiten
- ersten offiziellen Git-Tag erstellen
- erstes GitHub-Release veröffentlichen

### Zukünftige Entwicklung

Mögliche zukünftige Arbeiten sind:

- Unterstützung weiterer Linux-Distributionen
- zusätzliche Paketmanager-Backends
- weitere Verbesserungen der Benutzeroberfläche
- zusätzliche Berichtsfunktionen
- erweiterte betriebliche Automatisierung
- zusätzliche Sicherheitskontrollen
- weitere Testabdeckung

Neue Funktionen sollen die bestehenden Architekturgrenzen beibehalten.

---

## Was LUMS nicht ist

LUMS ist ausdrücklich nicht konzipiert als:

- universelle Remote-Shell
- Ersatz für APT, dpkg oder pacman
- vollständige Plattform für Konfigurationsmanagement
- Endpoint-Management-Suite für jedes Betriebssystem
- ausschließlich cloudbasierter Dienst
- unkontrolliertes Framework zur Befehlsausführung

LUMS konzentriert sich auf ein klar umrissenes Problem:

> **Kontrollierte Linux-Software- und Updateverwaltung mit persistentem Zustand und Nachvollziehbarkeit.**

---

## Entwicklungsphilosophie

LUMS folgt einem einfachen Entwicklungszyklus:

```text
Erstellen
   ↓
Testen
   ↓
Absichern
   ↓
Dokumentieren
```

Eine Funktion gilt nicht allein deshalb als fertig, weil sie in der Entwicklungsumgebung funktioniert.

Sie sollte außerdem:

- getestet
- sicherheitsgeprüft
- dokumentiert
- reproduzierbar
- verständlich
- bei Bedarf wiederherstellbar

sein.

---

## Änderungsphilosophie

Änderungen sollten bewusst vorgenommen werden.

Eine typische Änderung sollte folgende Fragen beantworten:

1. Welches Problem wird gelöst?
2. Welche Komponente sollte die Änderung verantworten?
3. Hat die Änderung Auswirkungen auf die Sicherheit?
4. Beeinflusst sie den persistenten Zustand?
5. Beeinflusst sie Clients?
6. Sind Dokumentationsänderungen erforderlich?
7. Welche Tests belegen, dass bestehende Funktionen weiterhin arbeiten?

Das verringert das Risiko, einen Teil des Systems zu korrigieren und dabei unbemerkt einen anderen Teil zu beschädigen.

---

## Entwicklungsablauf

Der bevorzugte Entwicklungsablauf ist:

```text
Verstehen
   ↓
Implementieren
   ↓
Testen
   ↓
Prüfen
   ↓
Härten
   ↓
Dokumentieren
   ↓
Regressionstest
```

Sicherheitskritische Änderungen werden zusätzlich überprüft, bevor sie als abgeschlossen gelten.

---

## Repository

Das Projekt-Repository wird auf GitHub gehostet:

**NovaForgeCtrl/LUMS**

Das Repository enthält den Quellcode der Anwendung, Clientkomponenten, Tests, Containerkonfiguration und Projektdokumentation.

---

## Dokumentationsumfang

Der aktuelle Dokumentationsumfang besteht aus:

```text
README.md
install.md
administration.md
security.md
troubleshooting.md
LUMS_Optional_Theme_System.md
```

Jedes Dokument hat einen klar definierten Zweck.

Das README bietet die Projektübersicht.

Die Installationsanleitung beschreibt die Bereitstellung.

Die Administrationsanleitung erläutert den laufenden Betrieb.

Die Sicherheitsanleitung dokumentiert Sicherheitsarchitektur und Prüfstatus.

Die Anleitung zur Fehlerbehebung enthält Diagnoseverfahren.

Das Dokument zu optionalen Themes behandelt die Architektur visueller Anpassungen.

---

## Lizenz

LUMS wird unter der MIT-Lizenz veröffentlicht.

Die Lizenz soll das Projekt offen und zugänglich halten und gleichzeitig Nutzung, Änderung und Weiterverbreitung gemäß den Lizenzbedingungen erlauben.

Den vollständigen Rechtstext findest du in der Lizenzdatei des Repositorys.

---

## Community und Beiträge

LUMS ist ein Open-Source-Projekt; Beiträge sind willkommen.

Hilfreiche Beiträge können sein:

- Fehlerberichte
- Sicherheitsmeldungen
- Verbesserungen der Dokumentation
- Tests
- Unterstützung weiterer Paketmanager
- Verbesserungen am Frontend
- Verbesserungen am Backend
- Verbesserungen der Bereitstellung

Beiträge sollten die Architektur- und Sicherheitsprinzipien des Projekts bewahren.

---

## Sicherheitsmeldungen

Sicherheitsprobleme sollten nicht wie gewöhnliche Funktionswünsche behandelt werden.

Bei der Meldung eines Sicherheitsproblems sollten genügend Informationen bereitgestellt werden, um das Problem reproduzieren und verstehen zu können, ohne unnötig sensible Informationen offenzulegen.

Sicherheitsrelevante Änderungen sollten vor dem Zusammenführen sorgfältig geprüft werden.

---

## Projektidentität

LUMS basiert auf einer einfachen Idee:

> **Linux-Updateverwaltung ohne unnötigen Lärm.**

Das Projekt versucht nicht, Komplexität zu verbergen, indem es vorgibt, Linux-Paketverwaltung sei einfach.

Stattdessen macht es die relevanten Zustände sichtbar:

```text
Was ist installiert?
       ↓
Was kann aktualisiert werden?
       ↓
Was soll geändert werden?
       ↓
Wer hat es angefordert?
       ↓
Was ist tatsächlich passiert?
       ↓
Welcher Zustand bleibt zurück?
```

Diese Informationen bilden die Grundlage einer kontrollierten Updateverwaltung.

---

## Gesamtarchitektur

Auf höchster Ebene lässt sich LUMS in fünf Ebenen unterteilen:

```text
┌───────────────────────────────────────────────┐
│                    UI                         │
│       Interaktion und Sichtbarkeit             │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                    API                        │
│ Authentifizierung, Autorisierung, Validierung  │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                 Persistenz                    │
│       Aufträge, Clients, Benutzer, Ergebnisse  │
│                   und Audit                    │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                    Agent                      │
│      Lokale Ausführung und Systemmeldungen     │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│              Native Linux-Werkzeuge            │
│               APT / dpkg / pacman              │
└───────────────────────────────────────────────┘
```

Jede Ebene hat eine bestimmte Verantwortung.

Die UI ermöglicht die Interaktion.

Die API setzt Richtlinien durch.

SQLite stellt den persistenten Zustand bereit.

Der Agent führt kontrollierte Aktionen auf den Clients aus.

Der native Paketmanager nimmt die eigentliche Systemänderung vor.

---

## Abschließender Grundsatz

LUMS basiert auf einem zentralen Grundsatz:

> **Systemzustand beobachten. Änderungen kontrollieren. Ergebnisse protokollieren.**

Dieser Grundsatz gilt für die Softwarearchitektur, die Update-Ausführung, das Sicherheitsmodell, die Wiederherstellungsmechanismen und die Dokumentation.

**Linux-Updateverwaltung ohne unnötigen Lärm.**
