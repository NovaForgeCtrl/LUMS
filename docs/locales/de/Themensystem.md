# LUMS — Optionales Themesystem

> **Ein LUMS · Viele Oberflächen · Dasselbe Backend**

LUMS bietet ein optionales clientseitiges Themesystem, mit dem sich das visuelle Erscheinungsbild der Benutzeroberfläche ändern lässt, ohne die zugrunde liegende Funktionalität von LUMS zu verändern.

Themes sind ausschließlich eine Darstellungsebene. Sie ersetzen, verändern oder umgehen weder das LUMS-Backend noch Authentifizierung, Autorisierung, Update-Ausführung, Paketverwaltung, Clientverwaltung, Auftragsverarbeitung oder Sicherheitskontrollen.

Das Themesystem macht LUMS an unterschiedliche visuelle Vorlieben anpassbar, während die Anwendung selbst einheitlich bleibt.

## Implementierungsstatus und maßgebliche Quelle

Die aktuelle Browserimplementierung befindet sich in `server/static/theme.js`. Sie unterstützt `standard`, `LUMSStadium`, `golf`, `nerd`, `geek` und `admin`, speichert die Auswahl unter `lums-theme` im Browser-`localStorage` und verwendet `standard` als Fallback, wenn die gespeicherte Kennung fehlt oder ungültig ist. Das Theme `nerd` startet den Matrix-Effekt und `geek` den Netzwerkeffekt. Die Theme-Auswahl ist eine Browsereinstellung, keine Kontoeinstellung und kein serverseitiger Autorisierungsstatus.

Diese Referenz enthält auch Designanforderungen und konzeptionelle Beispiele. Aussagen mit Begriffen wie „sollte“, „muss“ oder „zukünftig“ beschreiben Architekturleitlinien und belegen nicht, dass ein bestimmtes visuelles Merkmal oder Barrierefreiheitsverhalten implementiert ist. Prüfe das aktuelle Verhalten im Quellcode, bevor du ein Konzept als ausgelieferte Funktion behandelst.

---

## 1. Überblick

Das optionale Themesystem ermöglicht der LUMS-Weboberfläche mehrere visuelle Umgebungen mit demselben Anwendungs-Backend.

Ein Theme kann Folgendes verändern:

* Farben
* Typografie
* Hintergründe
* dekorative Elemente
* visuelle Hervorhebungen
* Erscheinungsbild der Navigation
* Animationen
* optionale visuelle Effekte
* seitenspezifische Darstellung

Ein Theme darf Folgendes nicht verändern:

* Benutzerberechtigungen
* verfügbare API-Endpunkte
* Authentifizierungsverhalten
* Autorisierungsentscheidungen
* CSRF-Schutz
* Client-Authentifizierung
* Update-Ausführung
* Paketverwaltungsberechtigungen
* Auftragsstatusbehandlung
* Audit-Protokollierung
* Datenbankverhalten
* Sicherheitsgrenzen

Das Prinzip ist einfach:

> **Themes ändern, wie LUMS aussieht, nicht, was LUMS tun darf.**

---

## 2. Designprinzipien

Das Themesystem folgt mehreren Prinzipien.

### 2.1 Optionalität

Themes sind eine optionale Frontend-Funktion.

LUMS bleibt vollständig funktionsfähig, auch wenn kein zusätzliches Theme ausgewählt ist.

Das Standard-Erscheinungsbild von LUMS dient als Standarddarstellung.

---

### 2.2 Clientseitigkeit

Die Theme-Auswahl gehört zum Frontend.

Ein Theme-Wechsel darf keine Änderung des serverseitigen Anwendungszustands erfordern.

Das ausgewählte Theme eines Benutzers ist daher eine Darstellungspräferenz und weder eine Kontoberechtigung noch eine Backend-Konfiguration.

---

### 2.3 Unabhängigkeit vom Backend

Alle Themes verwenden dasselbe LUMS-Backend.

Folgendes bleibt unabhängig vom ausgewählten Theme:

```text
Authentication
Authorization
RBAC
Client Management
Software Inventory
Update Detection
Package Management
Update Jobs
Job Recovery
Audit Logging
Database Operations
```

Das Backend bleibt die maßgebliche Quelle für alle sicherheits- und betriebskritischen Entscheidungen.

---

### 2.4 Keine Sicherheit durch Themes

Ein Theme darf niemals als Sicherheitsmechanismus verwendet werden.

Das Ausblenden einer Aktion in der Oberfläche erteilt oder entzieht beispielsweise keine Berechtigung.

Wenn ein Benutzer eine Aktion nicht ausführen darf, muss der Server sie unabhängig vom aktiven Theme ablehnen.

So wird verhindert, dass die Frontend-Darstellung zu einer Autorisierungsgrenze wird.

---

### 2.5 Robuster Fallback

Das Themesystem sollte immer einen gültigen Fallback bereitstellen.

Wenn:

* kein Theme ausgewählt wurde,
* ein gespeichertes Theme nicht mehr verfügbar ist,
* eine Theme-Kennung ungültig ist,
* ein Theme-Asset nicht geladen werden kann,

sollte LUMS auf die Standarddarstellung zurückfallen, statt die Oberfläche unbrauchbar zu machen.

---

## 3. Konzeptuelle Architektur

Das Themesystem lässt sich als separate Darstellungsebene um die bestehende LUMS-Anwendung herum betrachten.

```text
┌──────────────────────────────────────┐
│              LUMS UI                 │
│                                      │
│  ┌────────────────────────────────┐  │
│  │        Theme Presentation      │  │
│  │                                │  │
│  │ Standard / Stadium / Golf /    │  │
│  │ Nerd / Geek / Admin / ...      │  │
│  └────────────────────────────────┘  │
│                  │                   │
│                  ▼                   │
│        Common Frontend Logic        │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│             LUMS API                 │
│                                      │
│ Authentication / RBAC / Jobs /       │
│ Clients / Packages / Updates / Logs  │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│          LUMS Backend                │
│                                      │
│ Flask / SQLite / Job Processing /   │
│ Client Communication                 │
└──────────────────────────────────────┘
```

Die wichtige Grenze verläuft zwischen **Darstellung** und **Anwendungslogik**.

Themes gehören oberhalb dieser Grenze.

---

## 4. Lebenszyklus eines Themes

Konzeptionell läuft die Auswahl eines Themes folgendermaßen ab:

```text
User selects theme
        │
        ▼
Frontend stores selection
        │
        ▼
Theme initialization
        │
        ▼
Theme applied to UI
        │
        ▼
LUMS continues using
the same backend and permissions
```

Die Auswahl selbst erzeugt keine neue LUMS-Umgebung.

Es bleibt bei einer LUMS-Anwendung, einem Backend und einem Sicherheitsmodell.

---

## 5. Theme-Kennungen

Themes sollten stabile interne Kennungen verwenden, statt von ihren Anzeigenamen abhängig zu sein.

Zum Beispiel:

```text
standard
LUMSStadium
golf
nerd
geek
admin
```

Die Kennung ist ein Implementierungsdetail.

Der sichtbare Theme-Name kann unabhängig geändert werden, ohne dass Backend oder Anwendungsarchitektur angepasst werden müssen.

Wird eine Theme-Kennung entfernt oder umbenannt, sollte das Themesystem für Benutzer, bei denen die vorherige Kennung noch lokal gespeichert ist, einen Fallback bereitstellen.

---

## 6. Aufgabentrennung

Das Themesystem hat bewusst einen eng begrenzten Aufgabenbereich.

### Theme-Ebene

Zuständig für:

* visuelle Darstellung
* Theme-Auswahl
* themespezifische Gestaltung
* optionale visuelle Effekte
* themespezifische Frontend-Dekoration
* darstellungsbezogenes Verhalten zur Barrierefreiheit

### Gemeinsames Frontend

Zuständig für:

* Darstellung von Anwendungsdaten
* Aufrufe der LUMS-APIs
* Darstellung von Aufträgen und Softwareinformationen
* Verarbeitung von Benutzerinteraktionen
* Sichtbarkeit auf Darstellungsebene

### Backend

Zuständig für:

* Authentifizierung
* Autorisierung
* RBAC
* CSRF-Schutz
* Client-Authentifizierung
* Auftragserstellung
* Auftragsausführung
* Paketverwaltung
* Datenbankoperationen
* Audit-Protokollierung
* Sicherheitsentscheidungen

Diese Trennung ist grundlegend für das Design.

---

## 7. Sicherheitsgrenze

Das Themesystem ist **kein vertrauenswürdiger Code für Autorisierungszwecke**.

Auch wenn ein Theme ein Oberflächenelement verändert oder ausblendet, bleibt das Backend für die Validierung der angeforderten Aktion zuständig.

Konzeptionell:

```text
Frontend visibility
        ≠
Backend permission
```

Beispiel:

```text
Viewer
  │
  ├── Theme may display no package-management controls
  │
  └── Backend still rejects unauthorized package operations
```

Dasselbe Prinzip gilt für Verwaltungsfunktionen, Update-Aufträge, Clientverwaltung und alle anderen privilegierten Aktionen.

---

## 8. Betriebsprinzip

Das Themesystem sollte für die Betriebsarchitektur von LUMS ohne Auswirkungen bleiben.

Ein Theme-Wechsel darf Folgendes nicht erfordern:

* Neuerstellung der Datenbank
* Änderung der Clientkonfiguration
* Änderung der Client-Token
* Neustart von Update-Agenten
* Änderung von Update-Aufträgen
* Änderung von RBAC
* Änderung der Netzwerkkonfiguration
* Änderung des Paketverwaltungsverhaltens

Das Theme ist eine Darstellungspräferenz, keine Betriebskonfiguration.

---

## 9. Umfang der Dokumentation

Dieses Dokument beschreibt das optionale LUMS-Themesystem selbst.

Allgemeine LUMS-Themen sind separat dokumentiert:

* Installation und Bereitstellung → `install.md`
* Administration und Wartung → `administration.md`
* Fehlerbehebung → `troubleshooting.md`
* Sicherheitsarchitektur und Audits → `security.md`
* Allgemeiner Projektüberblick → `README.md`

Durch diese Trennung wird verhindert, dass die Theme-Dokumentation zu einem zweiten Installations- oder Administrationshandbuch wird.

---

## 10. Grundprinzip

Das optionale Themesystem lässt sich folgendermaßen zusammenfassen:

> **Ein LUMS. Ein Backend. Ein Sicherheitsmodell. Viele mögliche Oberflächen.**

# LUMS — Optionales Themesystem

## Teil 2 — Theme-Struktur und Auswahl

## 11. Theme-Struktur

Das optionale Themesystem trennt die Auswahl eines Themes von seiner tatsächlichen visuellen Darstellung.

Ein Theme besteht konzeptionell aus drei Ebenen:

```text
Theme Identifier
       │
       ▼
Theme Selection
       │
       ▼
Theme Presentation
```

Die Kennung legt fest, welches Theme ausgewählt wurde.

Der Auswahlmechanismus bestimmt, welches Theme derzeit aktiv sein soll.

Die Darstellungsebene wendet die entsprechende visuelle Konfiguration auf die LUMS-Oberfläche an.

Durch diese Trennung können Themes hinzugefügt oder entfernt werden, ohne die grundlegende Architektur der LUMS-Anwendung zu ändern.

---

## 12. Theme-Auswahl

Die Theme-Auswahl wird vom Frontend verwaltet.

Das ausgewählte Theme gilt als lokale Darstellungspräferenz und nicht als serverseitige Kontoeigenschaft.

Konzeptionell:

```text
User
 │
 ▼
Theme Selector
 │
 ▼
Selected Theme Identifier
 │
 ▼
Frontend Theme Initialization
 │
 ▼
Active Theme
```

Das Backend muss nicht wissen, welches visuelle Theme gerade ausgewählt ist.

Das bedeutet auch, dass ein Theme-Wechsel keine Auswirkungen auf andere Benutzer hat.

Zwei Benutzer können auf dieselbe LUMS-Instanz zugreifen und dabei völlig unterschiedliche visuelle Themes verwenden.

---

## 13. Lokale Theme-Präferenz

Das ausgewählte Theme kann lokal im Browser gespeichert werden.

Die lokale Speicherung dient dem Komfort:

```text
Browser
   │
   ├── Theme preference
   │
   └── LUMS application
```

Eine gespeicherte Theme-Auswahl ist als nicht vertrauenswürdiger clientseitiger Zustand zu behandeln.

Der Server darf sie niemals als Folgendes interpretieren:

* eine Rolle
* eine Berechtigung
* einen Authentifizierungsstatus
* eine Sicherheitseinstellung
* eine administrative Präferenz

Der Browser kann das Erscheinungsbild auswählen, aber nicht die Autorisierung steuern.

---

## 14. Theme-Initialisierung

Beim Laden der LUMS-Oberfläche ermittelt das Frontend, welches Theme aktiv sein soll.

Der konzeptionelle Ablauf ist:

```text
Page Load
   │
   ▼
Read Stored Theme
   │
   ▼
Is Theme Valid?
   │
   ├── Yes ──────► Apply Theme
   │
   └── No ───────► Use Standard Theme
```

Wenn keine Präferenz vorhanden ist, sollte die Standarddarstellung von LUMS verwendet werden.

Wird eine gespeicherte Kennung nicht mehr unterstützt, sollte derselbe Fallback greifen.

So wird verhindert, dass eine veraltete lokale Präferenz die Oberfläche beschädigt.

---

## 15. Standard-Theme

Das Standard-Theme von LUMS ist die Basisdarstellung.

Es bildet das Referenz-Erscheinungsbild, an dem optionale Themes ausgerichtet werden.

Das Standard-Theme sollte daher:

* funktionsfähig
* lesbar
* barrierefrei
* visuell vollständig
* unabhängig von optionalen dekorativen Assets

bleiben.

Optionale Themes dürfen keine Voraussetzung für den normalen LUMS-Betrieb werden.

---

## 16. Theme-Anwendung

Das Frontend kann das aktive Theme über einen gemeinsamen Anwendungszustand oder ein Theme-Attribut auf Root-Ebene darstellen.

Konzeptionell:

```html
<html data-theme="theme-id">
```

Die genaue Implementierung kann sich mit der Weiterentwicklung des Frontends ändern.

Entscheidend ist die architektonische Anforderung, dass das aktive Theme vom Frontend-Stilsystem einheitlich erkannt werden kann.

Dadurch bleibt themespezifisches Styling von der gemeinsamen Anwendungsstruktur getrennt.

---

## 17. Themespezifisches Styling

Theme-Styling sollte vorwiegend mit CSS umgesetzt werden, statt das Anwendungs-Markup zu duplizieren.

Konzeptionell:

```text
Common HTML
     │
     ├── Standard styling
     ├── Stadium styling
     ├── Golf styling
     ├── Nerd styling
     ├── Geek styling
     └── Admin styling
```

So bleiben dieselben Anwendungskomponenten in allen Themes verfügbar.

Eine Client-Tabelle bleibt beispielsweise unabhängig vom aktiven Theme eine Client-Tabelle.

Nur ihre Darstellung ändert sich.

---

## 18. Gemeinsame Anwendungskomponenten

Themes sollten keine unabhängigen Varianten der LUMS-Seiten erzeugen.

Folgendes Prinzip sollte gelten:

```text
One component
       │
       ├── Theme A
       ├── Theme B
       ├── Theme C
       └── Theme D
```

Stattdessen:

```text
Theme A → separate page
Theme B → separate page
Theme C → separate page
```

Das Duplizieren von Seiten würde die Wartung erheblich erschweren und könnte zu Verhaltensunterschieden zwischen Themes führen.

Ein Theme sollte daher die gemeinsame Oberfläche gestalten, statt die Anwendung selbst zu ersetzen.

---

## 19. Theme-Assets

Themes können bei Bedarf zusätzliche Frontend-Assets verwenden.

Mögliche Assets sind:

* Hintergrundbilder
* dekorative Grafiken
* Symbole
* Animationen
* visuelle Überlagerungen
* themespezifische Illustrationen

Assets bleiben Teil der Frontend-Darstellungsebene.

Sie dürfen Folgendes nicht enthalten:

* Zugangsdaten
* Client-Token
* geheime Schlüssel
* Datenbankdateien
* Authentifizierungsdaten
* private Betriebsdaten

Theme-Assets sind als öffentliche Frontend-Ressourcen zu behandeln.

---

## 20. Optionale visuelle Effekte

Einige Themes können zusätzliche visuelle Effekte bereitstellen.

Beispiele:

* animierte Hintergründe
* dekorative Netzwerkeffekte
* atmosphärische Bewegung
* thematische Oberflächenelemente
* dynamische visuelle Dekorationen

Solche Effekte müssen optional bleiben.

Sie dürfen niemals für den funktionalen Betrieb von LUMS erforderlich sein.

---

## 21. Reduzierte Bewegung

Visuelle Effekte sollten die Präferenz von Benutzern für reduzierte Bewegung berücksichtigen.

Werden animierte oder sich ständig verändernde Elemente verwendet, sollte das Themesystem ein geeignetes Verhalten für reduzierte Bewegung bereitstellen.

Konzeptionell:

```text
Normal motion
     │
     ├── animations enabled
     └── visual effects enabled

Reduced motion
     │
     ├── animations reduced or disabled
     └── essential interface remains functional
```

Barrierefreiheit hat Vorrang vor dekorativen Animationen.

Ein Theme sollte auch dann nutzbar bleiben, wenn visuelle Effekte deaktiviert sind.

---

## 22. Theme-Unabhängigkeit

Ein Theme-Wechsel darf keine betrieblichen Nebenwirkungen auslösen.

Zum Beispiel:

```text
Theme change
     │
     ├── No client restart
     ├── No agent restart
     ├── No job cancellation
     ├── No database migration
     ├── No token rotation
     └── No permission change
```

Das Themesystem ist bewusst vom Betriebslebenszyklus von LUMS isoliert.

---

## 23. Fehlerbehandlung bei Themes

Ein Theme sollte sicher fehlschlagen.

Kann ein themespezifisches Asset oder eine Darstellungskomponente nicht geladen werden, muss die gemeinsame LUMS-Oberfläche weiterhin nutzbar bleiben.

Der bevorzugte Wiederherstellungsweg ist:

```text
Theme error
    │
    ▼
Fallback to standard presentation
    │
    ▼
LUMS remains usable
```

Ein Darstellungsproblem darf nicht zu einem Verfügbarkeitsproblem der Anwendung werden.

---

## 24. Ein neues Theme hinzufügen

Ein neues Theme sollte die bestehende Trennung zwischen Anwendungsverhalten und Darstellung beibehalten.

Konzeptioneller Ablauf:

```text
1. Define theme identifier
2. Define visual design
3. Add theme styling
4. Add optional assets
5. Add theme to selection mechanism
6. Test normal pages
7. Test different RBAC roles
8. Test reduced-motion behavior
9. Test fallback behavior
10. Verify no backend behavior changed
```

Ein neues Theme ist erst dann vollständig, wenn die vorhandene LUMS-Funktionalität unverändert bleibt.

---

## 25. Ein Theme entfernen

Auch das Entfernen eines Themes sollte reibungslos behandelt werden.

Ist ein entferntes Theme noch lokal bei einem Benutzer gespeichert, sollte das Frontend erkennen, dass die Kennung nicht mehr verfügbar ist, und auf das Standard-Theme zurückfallen.

Das Entfernen eines visuellen Themes darf die LUMS-Oberfläche eines Benutzers daher nicht unbrauchbar machen.

---

## 26. Benennung von Themes

Theme-Namen sollten klar unterscheiden zwischen:

* interner Kennung
* Anzeigename
* visuellem Konzept

Zum Beispiel:

```text
Internal identifier:  standard
Display name:         Standard LUMS
```

Durch diese Trennung kann sich der sichtbare Wortlaut weiterentwickeln, ohne unnötige Änderungen an der internen Implementierung zu erfordern.

---

## 27. Aktuelles Theme-Konzept

Das optionale LUMS-Themesystem basiert auf mehreren visuellen Identitäten bei gleichbleibender Anwendung.

Die derzeit dokumentierten Theme-Konzepte sind:

| Kennung | Konzept |
| ------------- | ---------------- |
| `standard` | Standard-LUMS |
| `LUMSStadium` | LUMS-Stadion |
| `golf` | Golfclub |
| `nerd` | Nerd-Modus |
| `geek` | Geek-Labor |
| `admin` | Enterprise-Administration |

Diese Themes stehen für unterschiedliche visuelle Ausrichtungen, nicht für verschiedene LUMS-Editionen.

Sie gehören alle weiterhin zu derselben Anwendung.

---

## 28. Ein Backend, viele Oberflächen

Die Beziehung lässt sich abschließend so zusammenfassen:

```text
                     ┌── Standard
                     ├── Stadium
                     ├── Golf
                     ├── Nerd
                     ├── Geek
                     └── Admin
                           │
                           ▼
                    Common LUMS UI
                           │
                           ▼
                       LUMS API
                           │
                           ▼
                     LUMS Backend
```

Die Theme-Ebene endet an der Darstellungsgrenze.

Alles unterhalb dieser Grenze ist allen Themes gemeinsam.

# LUMS — Optionales Themesystem

## Teil 3 — Theme-Konzepte

## 29. Standard-LUMS

Das Standard-LUMS-Theme ist die Referenzdarstellung der Anwendung.

Es soll eine klare und funktionale Oberfläche bieten, ohne ein bestimmtes visuelles Konzept vorauszusetzen.

Das Standard-Theme sollte Folgendes priorisieren:

* Lesbarkeit
* klare Informationshierarchie
* vorhersehbare Navigation
* Barrierefreiheit
* geringe visuelle Ablenkung
* einheitliche Darstellung der Komponenten

Es ist die Fallback-Darstellung des Themesystems.

Das Standard-LUMS-Theme sollte daher auch dann nutzbar bleiben, wenn alle optionalen visuellen Themes nicht verfügbar sind.

---

## 30. LUMS-Stadion

**LUMS-Stadion** ist eine ausdrucksstärkere visuelle Interpretation der LUMS-Oberfläche.

Das Konzept verbindet Systemadministration mit einer vom Stadion inspirierten visuellen Identität.

Mögliche Gestaltungselemente:

* von Anzeigetafeln inspirierte Informationsfelder
* deutlichere visuelle Statusanzeigen
* ereignisorientierte Darstellung
* thematische Hintergründe
* Hervorhebung betrieblicher Zustände
* dekorative Stadion-Elemente

Funktional bleibt das Theme mit Standard-LUMS identisch.

Ein erfolgreiches Update bleibt ein erfolgreiches Update.

Ein fehlgeschlagener Auftrag bleibt ein fehlgeschlagener Auftrag.

Nur die Darstellung ändert sich.

---

## 31. Golfclub

Das Theme **Golfclub** bietet eine bewusst kontrastierende visuelle Identität.

Statt einer herkömmlichen Server- oder Infrastrukturästhetik verwendet die Oberfläche ein ruhigeres Freizeitkonzept.

Die visuelle Ausrichtung kann Folgendes betonen:

* klare Oberflächen
* zurückhaltende Dekoration
* Golf-inspirierte Elemente
* an Golfplätze angelehnte visuelle Metaphern
* ruhige Statusdarstellung
* dezente thematische Akzente

Das Konzept zeigt, dass LUMS nicht wie eine herkömmliche Administrationskonsole aussehen muss, um funktional zu bleiben.

Backend und Anwendungsverhalten bleiben unverändert.

---

## 32. Nerd-Modus

Der **Nerd-Modus** richtet sich an eine technischere und spielerischere Darstellung.

Das Konzept kann den technischen Charakter von LUMS durch Elemente wie diese betonen:

* vom Terminal inspirierte Gestaltung
* technische Terminologie
* systemorientierte visuelle Elemente
* entwicklerorientierte Darstellung
* diagnostische Ästhetik
* bewusst technische Dekoration

Die klare Informationshierarchie muss dennoch erhalten bleiben.

Eine spielerische Oberfläche darf das Verständnis betrieblicher Informationen nicht erschweren.

---

## 33. Geek-Labor

Das **Geek-Labor** steht für eine experimentellere technische Umgebung.

Das visuelle Konzept kann Folgendes kombinieren:

* Laborästhetik
* technische Experimente
* Infrastrukturvisualisierung
* Systemdiagramme
* wissenschaftlich oder technisch inspirierte Elemente
* experimentelle visuelle Effekte

Das Theme soll die Oberfläche wie ein Infrastrukturlabor wirken lassen und zugleich die gleiche LUMS-Funktionalität im Hintergrund bewahren.

Visuelle Experimente müssen von der Betriebsanwendung isoliert bleiben.

---

## 34. Enterprise-Administration

Das Theme **Enterprise-Administration** steht für eine zurückhaltendere Verwaltungsoberfläche.

Die visuelle Ausrichtung kann Folgendes betonen:

* strukturierte Informationen
* kompakte Layouts
* Verwaltungs-Dashboards
* klare Statusanzeigen
* hohe Informationsdichte
* weniger dekorative Elemente

Dieses Theme eignet sich besonders für Benutzer, die eine herkömmliche Administrationskonsolen-Optik bevorzugen.

Es gewährt keine zusätzlichen Verwaltungsrechte.

Der Name beschreibt das visuelle Konzept, keine Autorisierungsstufe.

---

## 35. Theme-Vergleich

Die Themes lassen sich als verschiedene visuelle Interpretationen derselben Anwendung betrachten:

| Theme | Visuelle Ausrichtung | Hauptmerkmal |
| ---------------- | --------------------------- | ------------------- |
| Standard-LUMS | Klar / funktional | Referenzoberfläche |
| LUMS-Stadion | Stadion / Ereignis | Ausdrucksstark |
| Golfclub | Freizeit / Ruhe | Entspannt |
| Nerd-Modus | Technisch / spielerisch | Entwicklerorientiert |
| Geek-Labor | Experimentell / technisch | Labor |
| Enterprise-Administration | Strukturiert / administrativ | Zurückhaltend |

Diese Tabelle beschreibt ausschließlich Darstellungskonzepte.

Sie beschreibt **keine** Unterschiede bei:

* Berechtigungen
* Funktionen
* API-Zugriff
* Clientzugriff
* Auftragsausführung
* Paketverwaltung
* Sicherheit

---

## 36. Dieselbe Oberfläche, andere Darstellung

Ein zentrales Designziel ist, dass dieselbe Anwendungskomponente in allen Themes wiedererkennbar bleibt.

Zum Beispiel:

```text id="5dhlf7"
Client List
   │
   ├── Standard presentation
   ├── Stadium presentation
   ├── Golf presentation
   ├── Nerd presentation
   ├── Geek presentation
   └── Enterprise presentation
```

Die zugrunde liegenden Clientdaten bleiben identisch.

Nur ihre Darstellung ändert sich.

Dasselbe gilt für:

* Softwareinventare
* verfügbare Updates
* Update-Aufträge
* Auftragsverlauf
* Benutzerinformationen
* Systemstatus
* Paketverwaltungsoberflächen

---

## 37. Betriebsstatus

Themes können unterschiedliche Betriebszustände visuell hervorheben.

Zum Beispiel:

```text id="5wyy17"
PENDING
RUNNING
SUCCESS
FAILED
```

Ein Theme kann diese Zustände unterschiedlich darstellen, ihre semantische Bedeutung muss jedoch einheitlich bleiben.

Das Theme darf Anwendungszustände nicht neu definieren.

Zum Beispiel:

```text id="j4i9qd"
SUCCESS ≠ "looks green"

SUCCESS = actual LUMS job state
```

Die visuelle Darstellung bildet lediglich den Backend-Zustand ab.

---

## 38. Fehlerdarstellung

Themes können auch die visuelle Darstellung von Fehlern ändern.

Fehlerinformationen müssen jedoch verständlich bleiben.

Ein Theme sollte nicht:

* wichtige Fehlerinformationen verbergen
* technische Informationen durch dekorativen Text ersetzen
* Warnungen von normalen Zuständen ununterscheidbar machen
* Betriebsfehler unterdrücken

Visuelle Gestaltung kann die Darstellung verbessern, darf aber keine Diagnoseinformationen entfernen, die zum Verständnis eines Problems erforderlich sind.

---

## 39. Einheitlichkeit von Statusangaben

Derselbe Status muss in allen Themes dieselbe semantische Bedeutung haben.

Zum Beispiel:

| Status | Bedeutung |
| ------- | ------------------------- |
| Ausstehend | Wartet auf Ausführung |
| Wird ausgeführt | Wird gerade verarbeitet |
| Erfolgreich | Erfolgreich abgeschlossen |
| Fehlgeschlagen | Ausführung fehlgeschlagen |

Ein Theme kann diese Zustände mit anderen Farben, Symbolen, Schriftbildern oder Layouts darstellen.

Die zugrunde liegende Bedeutung muss unverändert bleiben.

---

## 40. Themespezifische Dekoration

Dekorative Elemente sollten gegenüber betrieblichen Informationen zweitrangig bleiben.

Beispiele:

* Hintergründe
* Muster
* Illustrationen
* atmosphärische Effekte
* thematische Symbole
* visuelle Verzierungen

Folgende Rangfolge sollte eingehalten werden:

```text id="3m08d7"
Operational Information
        │
        ▼
Application Usability
        │
        ▼
Accessibility
        │
        ▼
Visual Decoration
```

Dekoration darf niemals Vorrang vor Informationen haben, die für den Betrieb von LUMS erforderlich sind.

---

## 41. Visuelle Informationsdichte

Verschiedene Themes können unterschiedliche visuelle Informationsdichten verwenden.

Zum Beispiel:

* Enterprise-Administration kann eine hohe Informationsdichte priorisieren.
* Standard-LUMS kann eine ausgewogene Lesbarkeit priorisieren.
* Der Golfclub kann mehr Freiraum verwenden.
* Der Nerd-Modus kann kompakte technische Elemente verwenden.
* Das Stadion-Theme kann große Statusbereiche hervorheben.
* Das Geek-Labor kann mehr visuellen Kontext bieten.

Diese Unterschiede betreffen ausschließlich die Darstellung.

Sie ändern weder Umfang noch Verbindlichkeit der zugrunde liegenden Daten.

---

## 42. Barrierefreiheit in allen Themes

Jedes Theme muss eine grundlegende Nutzbarkeit gewährleisten.

Dazu gehören:

* lesbarer Text
* ausreichende visuelle Unterscheidbarkeit
* nutzbare Bedienelemente
* verständliche Statusanzeigen
* Tastaturbedienbarkeit
* gut erkennbare Fokuszustände
* Kompatibilität mit der Präferenz für reduzierte Bewegung

Eine wichtige Zustandsinformation darf nicht ausschließlich durch Farbe vermittelt werden.

Ein fehlgeschlagener Auftrag sollte beispielsweise nicht nur daran erkennbar sein, dass er in einer bestimmten Farbe dargestellt wird.

---

## 43. Themespezifische Animationen

Themes können Animationen enthalten, wenn diese das visuelle Konzept unterstützen.

Beispiele:

* dezente Übergänge
* animierte Hintergründe
* Netzwerkeffekte
* Statusübergänge
* atmosphärische Dekoration

Animationen sollten gegenüber der Anwendung zweitrangig bleiben.

Sie sollten nicht:

* Interaktionen verhindern
* Bedienelemente verdecken
* dauerhaft von Betriebsdaten ablenken
* die Barrierefreiheit beeinträchtigen
* Backend-Vorgänge beeinflussen

---

## 44. Das lebendige Netzwerk

Einige LUMS-Themes können eine dynamische, netzwerkartige Darstellungsebene verwenden.

Das Konzept stellt LUMS als lebendige Infrastrukturumgebung dar:

```text id="7w1v8b"
Client ─────┐
            │
Client ─────┼──── LUMS
            │
Client ─────┘
```

Eine solche Visualisierung ist dekorativ, sofern sie nicht ausdrücklich mit tatsächlichen Anwendungsdaten verbunden ist.

Ein visuelles Netzwerk darf daher nicht als maßgebliche Netzwerktopologie verstanden werden, es sei denn, die Anwendung stellt diese Informationen ausdrücklich bereit.

Diese Unterscheidung ist wichtig:

> **Eine visuelle Darstellung ist nicht automatisch betriebliche Telemetrie.**

---

## 45. Dekorative Daten und echte Daten

Themespezifische visuelle Effekte müssen klar von echten LUMS-Daten getrennt bleiben.

Zum Beispiel:

```text id="z6i5j0"
Decorative node
    ≠
Real client

Animated connection
    ≠
Real network connection

Visual status effect
    ≠
Backend job state
```

So wird verhindert, dass Benutzer eine ästhetische Visualisierung mit tatsächlichen Systeminformationen verwechseln.

---

## 46. Theme-Identität

Jedes Theme sollte eine erkennbare Identität haben, ohne zu einem separaten Produkt zu werden.

Das Ziel lautet:

```text id="qv1fbe"
Different visual identity
          +
Same LUMS functionality
          =
Optional LUMS Theme
```

So bleibt das Themesystem spielerisch und flexibel, während die technische Integrität der Anwendung erhalten bleibt.

---

## 47. Theme-Designregel

Die wichtigste Designregel für alle Themes lautet:

> **Ein Theme darf ausdrucksstark, ungewöhnlich, technisch, spielerisch oder zurückhaltend sein — es muss aber immer LUMS bleiben.**

Unabhängig von der gewählten visuellen Darstellung muss die Anwendung als dasselbe System erkennbar bleiben.

# LUMS — Optionales Themesystem

## Teil 4 — Frontend-Implementierung und Barrierefreiheit

## 48. Frontend-Theme-Ebene

Das optionale Themesystem gehört vollständig zum LUMS-Frontend.

Seine Zuständigkeit ist auf die Darstellung und die Verarbeitung von Benutzerpräferenzen beschränkt.

Konzeptionell:

```text
┌─────────────────────────────────┐
│          LUMS Frontend          │
│                                 │
│  Common Application Logic       │
│              │                  │
│              ▼                  │
│       Theme Presentation        │
│              │                  │
│              ▼                  │
│       Browser Rendering         │
└─────────────────────────────────┘
```

Die Theme-Ebene ersetzt nicht die gemeinsame Frontend-Logik.

Stattdessen stellt sie eine zusätzliche Darstellungsebene darum herum bereit.

---

## 49. Theme-Initialisierung

Die Theme-Initialisierung sollte Teil des normalen Frontend-Startvorgangs sein.

Der konzeptionelle Ablauf:

```text
Frontend starts
      │
      ▼
Theme system initializes
      │
      ▼
Stored preference is evaluated
      │
      ▼
Theme availability is checked
      │
      ├── Valid → selected theme
      │
      └── Invalid → standard theme
      │
      ▼
LUMS interface rendered
```

Die Initialisierung sollte leichtgewichtig sein und darf nicht von der Verfügbarkeit des Backends abhängen.

Die visuelle Darstellung sollte auch dann geladen werden können, wenn ein späterer API-Aufruf fehlschlägt.

---

## 50. Theme-Zustand

Das aktive Theme ist Frontend-Zustand.

Es sollte daher anders behandelt werden als der Anwendungszustand.

### Theme-Zustand

Beispiele:

```text
Active visual theme
Reduced-motion preference
Visual presentation preferences
```

### Anwendungszustand

Beispiele:

```text
Logged-in user
User role
Client state
Package state
Update state
Job state
Audit state
```

Der Theme-Zustand darf den Anwendungszustand niemals überschreiben oder vortäuschen.

---

## 51. Theme-Attribut auf Root-Ebene

Ein Attribut auf Root-Ebene eignet sich als konzeptionelle Darstellung des aktiven Themes.

Zum Beispiel:

```html
<html data-theme="standard">
```

oder:

```html
<html data-theme="nerd">
```

CSS kann das aktive Theme anschließend als Selektor verwenden.

Die genaue Implementierung kann sich ändern, das architektonische Ziel bleibt jedoch gleich:

> **Eine Anwendungsstruktur, mehrere Darstellungsdefinitionen.**

---

## 52. CSS-Organisation

Themespezifisches Styling sollte klar vom gemeinsamen LUMS-Styling unterscheidbar bleiben.

Konzeptionell:

```text
Common styles
│
├── Layout
├── Forms
├── Tables
├── Navigation
├── Status elements
└── Shared components

Theme styles
│
├── Standard
├── Stadium
├── Golf
├── Nerd
├── Geek
└── Admin
```

Gemeinsame Styles sollten die funktionale Struktur definieren.

Theme-Styles sollten die visuelle Identität festlegen.

Das verringert Duplikate und erleichtert die spätere Wartung von Themes.

---

## 53. CSS-Variablen

Themesysteme können CSS Custom Properties verwenden, um semantische Werte von ihrer visuellen Darstellung zu trennen.

Zum Beispiel:

```css
:root {
    --lums-background: ...;
    --lums-surface: ...;
    --lums-text: ...;
    --lums-accent: ...;
}
```

Ein Theme kann dann eigene Werte bereitstellen:

```css
[data-theme="example"] {
    --lums-background: ...;
    --lums-surface: ...;
    --lums-text: ...;
    --lums-accent: ...;
}
```

Wichtig ist, dass Komponenten möglichst semantische Variablen verwenden, statt Theme-spezifische Werte fest zu codieren.

---

## 54. Gemeinsame Komponenten

Das Themesystem sollte gemeinsame Komponenten gestalten, statt sie zu duplizieren.

Typische Komponenten sind:

* Navigation
* Schaltflächen
* Formulare
* Tabellen
* Statusanzeigen
* Karten
* Dialoge
* Elemente der Paketverwaltung
* Elemente für Update-Aufträge
* Clientinformationen
* Systeminformationen

Dieselbe Komponente sollte unabhängig vom aktiven Theme funktional identisch bleiben.

---

## 55. Theme-Assets

Optionale Themes können eigene Assets verwenden.

Mögliche Asset-Kategorien:

```text
Images
Icons
Backgrounds
Decorative graphics
Fonts
Animation assets
Visual effects
```

Theme-Assets sollten Frontend-Ressourcen bleiben.

Sie dürfen keine sensiblen Anwendungsinformationen enthalten.

Insbesondere dürfen Theme-Assets niemals Folgendes enthalten:

* Passwörter
* geheime Schlüssel
* Client-Token
* Datenbankinhalte
* private Zertifikate
* Authentifizierungsdaten

---

## 56. Laden von Assets

Theme-Assets sollten nur geladen werden, wenn sie benötigt werden.

Ein Theme sollte nicht allein dadurch jede LUMS-Seite unnötig belasten, dass es vorhanden ist.

Wenn möglich:

```text
Selected theme
      │
      ▼
Required assets
      │
      ▼
Browser
```

statt:

```text
All themes
      │
      ▼
All assets loaded simultaneously
```

Das wird umso wichtiger, je mehr Themes und visuelle Effekte hinzukommen.

---

## 57. Theme-Leistung

Visuelle Anpassungen dürfen die Nutzbarkeit von LUMS nicht wesentlich verschlechtern.

Besonders zu beachten sind:

* große Hintergrundbilder
* dauerhaft animierte Elemente
* Canvas-Effekte
* wiederholte DOM-Aktualisierungen
* aufwendige visuelle Filter
* unnötige Netzwerkanfragen

Betriebsseiten wie Clientlisten, Softwareinventare und Ansichten für Update-Aufträge sollten reaktionsschnell bleiben.

---

## 58. Dekoratives JavaScript

Ein Theme kann JavaScript für visuelle Effekte verwenden.

Beispiele:

* animierte Hintergründe
* Netzwerkvisualisierungen
* dynamische Dekorationen
* themespezifische Interaktionen

Dieses JavaScript sollte von der betrieblichen Anwendungslogik isoliert bleiben.

Ein dekoratives Skript darf niemals zuständig sein für:

* Autorisierung
* Auftragserstellung
* Paketinstallation
* Paketentfernung
* Update-Ausführung
* Client-Authentifizierung
* Audit-Protokollierung

Die Unterscheidung muss klar bleiben:

```text
Theme JavaScript
      ≠
LUMS operational JavaScript
```

---

## 59. Netzwerkvisualisierung

Wird in einem Theme eine netzwerkartige Visualisierung verwendet, sollte sie als Darstellungskomponente behandelt werden.

Zum Beispiel:

```text
Canvas / Visual Layer
        │
        ▼
Decorative Network
        │
        ▼
Theme Presentation
```

Sofern die Visualisierung nicht ausdrücklich mit maßgeblichen LUMS-Daten verbunden ist, sollte sie nicht den Eindruck erwecken, den tatsächlichen Netzwerkzustand abzubilden.

Dadurch wird verhindert, dass dekorative Grafiken mit Überwachung oder Telemetrie verwechselt werden.

---

## 60. Reduzierte Bewegung

Themes mit Animationen sollten Präferenzen für reduzierte Bewegung unterstützen.

Das bevorzugte Verhalten lässt sich konzeptionell so darstellen:

```text
prefers-reduced-motion: reduce
            │
            ▼
Reduce or disable decorative motion
```

Die wesentliche Funktionalität muss unverändert bleiben.

Reduzierte Bewegung sollte sich nur auf die Darstellung auswirken.

---

## 61. Fokus und Tastaturnavigation

Theme-Styling muss die Bedienbarkeit per Tastatur erhalten.

Wichtige interaktive Elemente sollten sichtbare Fokuszustände behalten.

Themes sollten Fokusrahmen nicht entfernen, ohne eine ebenso gut sichtbare Alternative bereitzustellen.

Zum Beispiel:

```text
Keyboard focus
      │
      ▼
Clearly visible control state
```

Das gilt für:

* Navigation
* Schaltflächen
* Links
* Formularfelder
* Auswahlfelder
* Dialoge
* Bedienelemente der Paketverwaltung

---

## 62. Unabhängigkeit von Farbe

Wichtige Informationen dürfen nicht ausschließlich von Farbe abhängen.

Zum Beispiel:

```text
FAILED
```

sollte auch dann durch Text, Symbole, Struktur oder einen anderen barrierefreien Hinweis verständlich bleiben, wenn die Farben des Themes nicht verfügbar sind.

Das ist besonders wichtig, weil Themes sehr unterschiedliche Farbpaletten verwenden können.

---

## 63. Kontrast

Jedes Theme sollte ausreichenden Kontrast sicherstellen zwischen:

* Text und Hintergründen
* Bedienelementen und Hintergründen
* Statusanzeigen und umgebenden Elementen
* fokussierten Elementen und ihrer Umgebung

Eine interessante Farbpalette ersetzt keine gut lesbaren Informationen.

Wenn Theme-Farben mit Anforderungen an die Barrierefreiheit kollidieren, hat Lesbarkeit Vorrang.

---

## 64. Theme-Auswahl in der Oberfläche

Der Theme-Auswahldialog selbst ist Teil der gemeinsamen LUMS-Oberfläche.

Er sollte unabhängig vom jeweils aktiven Theme verständlich bleiben.

Konzeptionell:

```text
Theme selector
      │
      ├── Standard LUMS
      ├── LUMS Stadium
      ├── Golf Club
      ├── Nerd Mode
      ├── Geek Lab
      └── Enterprise Admin
```

Die Auswahl eines anderen Themes sollte die Darstellung aktualisieren, ohne die aktuelle LUMS-Sitzung oder den Betriebszustand zu ändern.

---

## 65. Unabhängigkeit von der Sitzung

Ein Theme-Wechsel darf den Benutzer nicht abmelden.

Er darf nicht:

* die Sitzung ungültig machen
* die Rolle ändern
* Client-Token rotieren
* den serverseitigen Authentifizierungszustand verändern

Die Theme-Präferenz ist von der Authentifizierung getrennt.

```text
Theme change
     │
     └── Session remains unchanged
```

---

## 66. Unabhängigkeit von RBAC

Themes müssen unabhängig von RBAC bleiben.

Zum Beispiel:

```text
Administrator
     │
     └── sees functionality permitted to administrators

Operator
     │
     └── sees functionality permitted to operators

Viewer
     │
     └── sees functionality permitted to viewers
```

Das ausgewählte Theme ändert diese Berechtigungen nicht.

Ein Viewer wird durch das Theme Enterprise-Administration nicht zum Administrator.

Ein Administrator verliert durch den Nerd-Modus keine Verwaltungsrechte.

Das Backend bleibt in jedem Fall maßgeblich.

---

## 67. Fehlerisolierung

Ein Fehler in einer optionalen visuellen Funktion sollte den Kernbetrieb von LUMS nicht beeinträchtigen.

Fällt beispielsweise eine dekorative Animation aus:

```text
Animation failure
      │
      ▼
Theme remains usable
      │
      ▼
LUMS remains operational
```

Wo möglich, sollten visuelle Funktionen unabhängig von der Anwendungsfunktionalität ausfallen können.

Das ist besonders für optionale Effekte wie animierte Hintergründe oder Netzwerkvisualisierungen wichtig.

---

## 68. Browserkompatibilität

Das Themesystem sollte Browserfunktionen verwenden, die von den Browsern der vorgesehenen LUMS-Bereitstellungsumgebung unterstützt werden.

Ist eine visuelle Funktion nicht verfügbar, sollte die Oberfläche elegant zurückfallen, statt unbrauchbar zu werden.

Die Standarddarstellung sollte der grundlegende Fallback bleiben.

---

## 69. Implementierungsprinzip

Die Implementierung lässt sich so zusammenfassen:

```text
Common HTML
     +
Common LUMS JavaScript
     +
Theme selection
     +
Theme-specific CSS/assets
     =
Optional visual layer
```

Folgendes muss außerhalb der Theme-Ebene bleiben:

```text
Authentication
Authorization
Database
Jobs
Package management
Client authentication
Audit logging
Security decisions
```

Diese Trennung lässt dem Themesystem genug Raum für ausdrucksstarke Gestaltung und verhindert zugleich eine Kopplung an das Kernverhalten von LUMS.

# LUMS — Optionales Themesystem

## Teil 5 — Sicherheit, Tests und Entwicklung

## 70. Sicherheitsgrenze

Das Themesystem ist Teil des Frontends und läuft daher in einer nicht vertrauenswürdigen Clientumgebung.

Der Browser steuert die Darstellungsebene.

Der Browser steuert **nicht** die Autorisierung in LUMS.

Die Sicherheitsgrenze bleibt:

```text id="h8e2ks"
Browser
   │
   │ untrusted presentation
   ▼
LUMS API
   │
   │ authoritative validation
   ▼
LUMS Backend
```

Alle sicherheitsrelevanten Entscheidungen müssen daher weiterhin serverseitig getroffen werden.

---

## 71. Theme-Auswahl ist keine Autorisierung

Ein ausgewähltes Theme darf niemals als Autorisierungssignal interpretiert werden.

Zum Beispiel:

```text id="8u3r8v"
data-theme="admin"
```

bedeutet nicht, dass der aktuelle Benutzer Administrator ist.

Das Wort `admin` in einer Theme-Kennung dient ausschließlich der Beschreibung.

Die tatsächliche Rolle des Benutzers muss immer aus der authentifizierten Anwendungssitzung und der serverseitigen Autorisierungslogik stammen.

---

## 72. Sichtbarkeit im Frontend ist keine Sicherheit

Ein Theme oder ein Frontend-Skript kann ein Oberflächenelement ausblenden.

Das ist für die Darstellung nützlich.

Für eine Zugriffskontrolle reicht es nicht aus.

Zum Beispiel:

```text id="7m8c6w"
Hidden button
      ≠
Unauthorized operation prevented
```

Der entsprechende API-Endpunkt muss die Berechtigungen des Benutzers unabhängig davon überprüfen.

Das gilt für alle privilegierten Funktionen von LUMS.

---

## 73. Theme-Assets sind öffentlich

Frontend-Assets sind als öffentlich zugänglich für alle Personen zu betrachten, die auf die LUMS-Weboberfläche zugreifen können.

Daher dürfen Theme-Dateien niemals Geheimnisse enthalten.

Folgendes darf niemals in Theme-Assets abgelegt werden:

```text id="1zjz7n"
Passwords
API secrets
Client tokens
Private keys
Database files
Session secrets
Authentication credentials
```

Informationen, die vertraulich bleiben müssen, gehören nicht in ein Theme-Asset.

---

## 74. Keine Backend-Geheimnisse in Themes

Theme-JavaScript darf keine Server-Zugangsdaten oder privilegierten API-Daten enthalten.

Wenn erforderlich, sollte ein Theme über die vorhandene Frontend-Anwendungsebene kommunizieren.

Es darf keinen alternativen Authentifizierungsmechanismus einführen.

Es gilt folgender Grundsatz:

> **Themes nutzen Darstellungsdaten; sie erzeugen keine Sicherheitszugangsdaten.**

---

## 75. Cross-Site Request Forgery

Theme-Funktionen dürfen den vorhandenen CSRF-Schutz nicht umgehen.

Stellt ein Theme ein Oberflächenelement bereit, das eine geschützte Anfrage auslöst, muss die Anfrage dieselben Sicherheitsanforderungen erfüllen wie die gemeinsame LUMS-Oberfläche.

Visueller Code erhält keine Ausnahme.

---

## 76. API-Nutzung

Ein Theme sollte keine eigene operative API-Logik direkt implementieren.

Wenn Anwendungsdaten benötigt werden, sollte es die etablierten LUMS-Frontend- und Anwendungsmechanismen verwenden.

So werden mehrere unabhängige Implementierungen der folgenden Dinge verhindert:

* Authentifizierung
* API-Anfragen
* Fehlerbehandlung
* Annahmen zur Autorisierung
* Auftragsverarbeitung

Die gemeinsame Anwendungslogik bleibt die maßgebliche Frontend-Integrationsschicht.

---

## 77. Theme-Isolierung

Ein Theme sollte entfernt werden können, ohne die Kernfunktionen von LUMS zu entfernen.

Konzeptionell:

```text id="3m1o8q"
Remove optional theme
        │
        ▼
Standard LUMS remains
        │
        ▼
Application remains operational
```

So sind optionale Themes tatsächlich optional.

---

## 78. Sicherheitstests

Sicherheitstests sollten nachweisen, dass Theme-Änderungen das Sicherheitsmodell von LUMS nicht verändern.

Relevante Prüfungen:

* Viewer bleibt Viewer
* Operator bleibt Operator
* Administrator bleibt Administrator
* geschützte API-Endpunkte bleiben geschützt
* CSRF-Schutz bleibt aktiv
* Client-Authentifizierung bleibt unverändert
* Berechtigungen für Update-Aufträge bleiben unverändert
* Berechtigungen für die Paketverwaltung bleiben unverändert
* Audit-Protokollierung bleibt unverändert

Das Theme selbst darf niemals als Beleg dafür dienen, dass eine Aktion sicher ist.

---

## 79. Funktionstests für Themes

Jedes Theme sollte mit der gemeinsamen Anwendung getestet werden.

Mindestens:

```text id="9w6h1m"
Login
Client list
Client details
Installed software
Available updates
Update jobs
Job history
Package management
User management
System maintenance
Logout
```

Welche Funktionen verfügbar sind, hängt von der Rolle des authentifizierten Benutzers ab.

Der Test soll sicherstellen, dass die Darstellung des Themes die normale Anwendungsfunktionalität nicht beeinträchtigt.

---

## 80. RBAC-Tests für Themes

Theme-Tests sollten alle relevanten Rollen umfassen.

Eine grundlegende Matrix:

| Rolle | Theme-Tests |
| ------------- | ------------- |
| Administrator | Erforderlich |
| Operator | Erforderlich |
| Viewer | Erforderlich |

Prüfe für jede Rolle, dass ein Theme-Wechsel die zulässigen Funktionen nicht verändert.

Zum Beispiel:

```text id="3n5p2m"
Viewer + Nerd Mode
        =
Viewer permissions

Viewer + Enterprise Admin
        =
Viewer permissions
```

Das visuelle Theme darf das Ergebnis nicht verändern.

---

## 81. Tests für den Theme-Wechsel

Der Wechsel zwischen Themes sollte wiederholt getestet werden.

Beispielsequenz:

```text id="gk2j7m"
Standard
   ↓
Stadium
   ↓
Golf
   ↓
Nerd
   ↓
Geek
   ↓
Admin
   ↓
Standard
```

Die Anwendung sollte während der gesamten Sequenz nutzbar bleiben.

Besonders zu beachten sind:

* Layoutänderungen
* Tabellen
* Navigation
* Dialoge
* Formulare
* Statusanzeigen
* lange Texte
* responsives Verhalten

---

## 82. Persistenztests

Wird die Theme-Präferenz lokal gespeichert, teste Folgendes:

1. Wähle ein Theme aus.
2. Lade die Seite neu.
3. Prüfe, ob das Theme weiterhin ausgewählt ist.
4. Schließe den Browser.
5. Öffne LUMS erneut.
6. Prüfe, ob die Präferenz weiterhin korrekt behandelt wird.
7. Entferne oder entwerte das gespeicherte Theme.
8. Prüfe, ob auf das Standard-Theme zurückgefallen wird.

Der gespeicherte Wert darf niemals als Anwendungs-Sicherheitszustand gelten.

---

## 83. Tests mit ungültigen Themes

Eine ungültige Theme-Kennung darf die Oberfläche nicht beschädigen.

Zum Beispiel:

```text id="4j5cqn"
unknown-theme
```

sollte zu einem sicheren Fallback führen, nicht zu einer unbrauchbaren Seite.

Das gewünschte Verhalten:

```text id="5x9h2f"
Invalid theme
     │
     ▼
Standard theme
     │
     ▼
LUMS remains usable
```

---

## 84. Tests bei Asset-Fehlern

Auch das Fehlerverhalten optionaler Assets sollte getestet werden.

Beispiele:

* fehlendes Bild
* nicht verfügbare Animation
* ungültiger Asset-Pfad
* nicht unterstützte visuelle Funktion
* JavaScript-Fehler in einer optionalen Dekoration

Die gemeinsame Anwendung sollte nach Möglichkeit weiterhin nutzbar bleiben.

---

## 85. Tests für reduzierte Bewegung

Bei Themes mit Animationen sind sowohl normale Umgebungen als auch Umgebungen mit reduzierter Bewegung zu testen.

```text id="l1h4nb"
Normal motion
     │
     └── Theme effects available

Reduced motion
     │
     └── Effects reduced or disabled
```

Wichtige Bedienelemente der Anwendung müssen in beiden Fällen vollständig funktionieren.

---

## 86. Responsive Tests

Themes sollten bei verschiedenen Ansichtsfenstergrößen getestet werden.

Mindestens:

* Desktop
* Tablet-Ansichtsfenster
* schmales Ansichtsfenster in Mobilgerätegröße

Die visuelle Identität darf nicht auf Kosten nutzbarer Bedienelemente oder lesbarer Anwendungsdaten gehen.

Besonders zu beachten sind:

* Navigation
* Tabellen
* Aktionsschaltflächen
* Bedienelemente der Paketverwaltung
* Statusinformationen zu Aufträgen
* Dialoge
* Theme-Auswahlfelder

---

## 87. Leistungstests

Die Auswirkungen visueller Effekte auf die Browserleistung sollten bewertet werden.

Relevante Messgrößen:

* Seitenladezeit
* Reaktionsfähigkeit der Darstellung
* CPU-Auslastung
* Speichernutzung
* Flüssigkeit von Animationen
* wiederholte DOM-Aktualisierungen
* Netzwerkanfragen

Themes sollten die Darstellung verbessern und nicht zu einem Leistungsengpass werden.

---

## 88. Entwicklungsablauf

Ein neues Theme sollte nach Möglichkeit unabhängig von Backend-Änderungen entwickelt werden.

Empfohlener Ablauf:

```text id="1i8qz6"
Design
   ↓
Frontend implementation
   ↓
Theme selector integration
   ↓
Accessibility review
   ↓
Functional testing
   ↓
RBAC testing
   ↓
Fallback testing
   ↓
Performance review
   ↓
Documentation
```

Backend-Änderungen sollten nur bei einem echten Anwendungsbedarf eingeführt werden.

Ein visuelles Theme sollte normalerweise keine Änderungen am Backend erfordern.

---

## 89. Entwicklungsregeln

Bei der Entwicklung eines Themes:

1. Vorhandene LUMS-Komponenten wiederverwenden.
2. Seiten nicht duplizieren.
3. Themespezifisches Styling isolieren.
4. Dekoratives JavaScript von der Betriebslogik trennen.
5. Keine Authentifizierungslogik einführen.
6. Keine Autorisierungslogik einführen.
7. Keine Geheimnisse offenlegen.
8. Barrierefreiheit erhalten.
9. Verhalten bei reduzierter Bewegung erhalten.
10. Alle relevanten Rollen testen.
11. Den Standard-Fallback testen.
12. Neue Assets und ihr Verhalten dokumentieren.

---

## 90. Änderung verifizieren

Bevor eine Theme-Änderung als abgeschlossen gilt, müssen Darstellung und Funktionalität überprüft werden.

Eine sinnvolle Prüfsequenz:

```text id="i1v9yb"
Theme changed
      │
      ▼
Visual inspection
      │
      ▼
Page functionality
      │
      ▼
Role behavior
      │
      ▼
API behavior
      │
      ▼
Browser console
      │
      ▼
Regression tests
```

Ein Theme ist nicht allein deshalb vollständig, weil es korrekt aussieht.

Das Verhalten von LUMS muss ebenfalls unverändert bleiben.

---

## 91. Regressionsprinzip

Bei der Theme-Entwicklung sollte dasselbe allgemeine Projektprinzip gelten wie bei anderen Änderungen an LUMS:

> **Ändern → Testen → Verifizieren → Dokumentieren**

Auch eine visuelle Änderung kann funktionale Regressionen verursachen.

Beispiele:

* ausgeblendete Schaltflächen
* unlesbarer Text
* fehlerhaftes Layout
* nicht barrierefreie Bedienelemente
* JavaScript-Konflikte
* fehlende Assets
* falsche Selektoren
* Fehler im Mobilgerätelayout

Tests sind daher Bestandteil der Theme-Entwicklung und kein optionaler letzter Schritt.

---

## 92. Fehlerbehebung: Theme wird nicht geladen

Wenn das ausgewählte Theme nicht angezeigt wird:

1. Lade die Seite neu.
2. Prüfe, ob das Standard-Theme geladen wird.
3. Prüfe die Browserkonsole.
4. Prüfe, ob die ausgewählte Theme-Kennung gültig ist.
5. Prüfe, ob erforderliche Theme-Assets verfügbar sind.
6. Suche nach JavaScript-Fehlern.
7. Lösche bei Bedarf die lokale Theme-Präferenz.
8. Lade die Seite neu und überprüfe den Standard-Fallback.

Ändere nicht die Sicherheitskonfiguration des Backends, um ein Frontend-Theme-Problem zu beheben.

---

## 93. Fehlerbehebung: Theme beschädigt das Layout

Wenn ein Theme Layoutprobleme verursacht:

1. Wechsle zum Standard-LUMS-Theme.
2. Bestätige, dass die gemeinsame Oberfläche funktioniert.
3. Ermittle die betroffene Komponente.
4. Prüfe das themespezifische CSS.
5. Prüfe das responsive Verhalten.
6. Prüfe die Browserkonsole auf Fehler.
7. Korrigiere das themespezifische Styling.
8. Teste andere Themes erneut.

Das Standard-Theme bietet einen wichtigen diagnostischen Vergleich.

---

## 94. Fehlerbehebung: Theme verursacht JavaScript-Fehler

Wenn themespezifisches JavaScript Fehler verursacht:

1. Wechsle zum Standard-Theme.
2. Prüfe die normale LUMS-Funktionalität.
3. Ermittle das fehlerhafte Theme-Skript.
4. Stelle fest, ob der Fehler dekorativ oder anwendungsbezogen ist.
5. Behebe den themespezifischen Fehler.
6. Prüfe, ob das gemeinsame LUMS-JavaScript unbeeinträchtigt bleibt.
7. Teste den Theme-Wechsel erneut.

Betriebliches JavaScript sollte nicht allein geändert werden, um einen dekorativen Theme-Fehler auszugleichen.

---

## 95. Fehlerbehebung: Theme-Präferenz ist ungültig

Wenn ein altes oder ungültiges Theme lokal gespeichert ist:

```text id="b9n8wq"
Invalid stored preference
        │
        ▼
Fallback to Standard
        │
        ▼
Select a valid theme
```

Die bevorzugte Lösung ist ein sicherer Fallback und kein manueller Eingriff ins Backend.

---

## 96. Dokumentation der Themes

Für jedes neue Theme sollten dokumentiert werden:

* interne Kennung
* Anzeigename
* visuelles Konzept
* erforderliche Assets
* optionale visuelle Effekte
* Überlegungen zur Barrierefreiheit
* Verhalten bei reduzierter Bewegung
* bekannte Einschränkungen

Implementierungsspezifische Dokumentation sollte den tatsächlich aktuellen Code beschreiben und nicht auf Annahmen darüber beruhen, wie das Theme funktionieren könnte.

---

## 97. Aktuelle Themes

Derzeit sind folgende Theme-Konzepte dokumentiert:

```text id="r0w4u5"
standard       → Standard LUMS
LUMSStadium    → LUMS Stadium
golf           → Golf Club
nerd           → Nerd Mode
geek           → Geek Lab
admin          → Enterprise Admin
```

Die Theme-Auswahl lässt sich erweitern.

Weitere Themes können hinzugefügt werden, ohne die zugrunde liegende LUMS-Architektur zu ändern, sofern die Trennung von Darstellung und Anwendungsverhalten erhalten bleibt.

---

## 98. Entwicklungsprinzip

Das optionale Themesystem sollte eine kontrollierte Frontend-Erweiterung bleiben.

Es soll LUMS ausdrucksstärker und anpassbarer machen, ohne den betrieblichen Aufwand der Anwendung zu erhöhen.

Die bevorzugte Architektur lautet daher:

```text id="l2e8o9"
Common LUMS
     │
     ├── Common functionality
     ├── Common security
     ├── Common backend
     └── Common application state
              │
              ▼
       Optional Theme Layer
              │
       ┌──────┼──────┐
       ▼      ▼      ▼
    Theme A Theme B Theme C
```

Die gemeinsame Anwendung bleibt die Grundlage.

Themes bleiben optionale Erweiterungen.

# LUMS — Optionales Themesystem

## Teil 6 — Wartung, Erweiterung und abschließender Status

## 99. Theme-Wartung

Die Wartung von Themes sollte nach Möglichkeit von der Wartung des LUMS-Kerns getrennt bleiben.

Eine visuelle Theme-Aktualisierung sollte normalerweise nur Frontend-Ressourcen betreffen.

Typische Änderungen umfassen:

* CSS-Anpassungen
* visuelle Assets
* themespezifisches JavaScript
* Verbesserungen der Barrierefreiheit
* Korrekturen des responsiven Layouts
* Anpassungen von Animationen
* Änderungen an Theme-Namen oder Darstellung

Eine Theme-Aktualisierung sollte keine Änderungen erfordern an:

* Clientkonfiguration
* Client-Token
* Datenbankschema
* Update-Aufträgen
* Paketverwaltungslogik
* Authentifizierung
* RBAC
* serverseitigen Sicherheitskontrollen

Erfordert eine Theme-Änderung unerwartet solche Anpassungen, sollte die Abhängigkeit vor dem weiteren Vorgehen überprüft werden.

---

## 100. Theme-Aktualisierungen

Theme-Aktualisierungen sollten dem normalen LUMS-Entwicklungsprozess folgen:

```text id="2p7z9r"
Modify
   ↓
Test
   ↓
Verify
   ↓
Document
```

Für größere Änderungen:

```text id="p7l5me"
Design
   ↓
Implementation
   ↓
Functional testing
   ↓
Accessibility testing
   ↓
RBAC regression testing
   ↓
Performance review
   ↓
Documentation
```

Ein Theme sollte nicht allein deshalb als abgeschlossen gelten, weil das visuelle Ergebnis korrekt aussieht.

---

## 101. Ein neues Theme hinzufügen

Ein neues Theme lässt sich hinzufügen, ohne das LUMS-Backend zu ändern.

Empfohlener Ablauf:

### Schritt 1 — Konzept festlegen

Beschreibe:

* visuelle Identität
* angestrebten Stil
* Typografie
* Farben
* dekorative Elemente
* optionale Animationen

### Schritt 2 — Kennung festlegen

Wähle eine stabile interne Kennung.

### Schritt 3 — Darstellung implementieren

Füge die erforderlichen Styles und Assets hinzu.

### Schritt 4 — Auswahl integrieren

Mache das Theme über den gemeinsamen Theme-Auswahldialog verfügbar.

### Schritt 5 — Testen

Überprüfe:

* normale Seiten
* interaktive Bedienelemente
* responsive Layouts
* Barrierefreiheit
* reduzierte Bewegung
* alle relevanten RBAC-Rollen
* Fallback-Verhalten

### Schritt 6 — Dokumentieren

Halte das Theme und die relevanten Implementierungsdetails fest.

---

## 102. Ein Theme entfernen

Das Entfernen eines Themes sollte als Kompatibilitätsänderung für Benutzer behandelt werden, bei denen das Theme noch lokal ausgewählt ist.

Das Frontend sollte daher eine veraltete Kennung sicher behandeln:

```text id="x4e7p1"
Old theme identifier
       │
       ▼
Theme no longer available
       │
       ▼
Standard LUMS
```

Das Entfernen eines browserseitigen Merkmals darf niemals allein deshalb eine Datenbankmigration erfordern.

---

## 103. Ein Theme umbenennen

Ein Anzeigename kann normalerweise unabhängig von der internen Kennung geändert werden.

Zum Beispiel:

```text id="8q4n1k"
Internal identifier
        │
        └── remains stable

Display name
        │
        └── may change
```

Ändert sich die interne Kennung selbst, kann für bestehende lokale Präferenzen eine Migration oder Kompatibilitätszuordnung erforderlich sein.

Wenn möglich, sollten Kennungen stabil bleiben.

---

## 104. Theme-Kompatibilität

Themes sollten mit Änderungen an der gemeinsamen LUMS-Oberfläche kompatibel bleiben.

Wird eine neue gemeinsame Komponente eingeführt, sollte geprüft werden, ob bestehende Themes Folgendes aufweisen:

* fehlendes Styling
* fehlerhafte Abstände
* unlesbaren Text
* falsche Farben
* fehlendes responsives Verhalten
* falsche Fokuszustände
* nicht barrierefreie Bedienelemente

Eine neue Backend-Funktion erfordert nicht automatisch eine neue Theme-Funktion.

Die gemeinsame Anwendung bleibt die maßgebliche Quelle.

---

## 105. Neue LUMS-Funktionen

Erhält LUMS eine neue Funktion, sollte die Theme-Unterstützung normalerweise erst bewertet werden, nachdem die gemeinsame Funktionalität umgesetzt wurde.

Empfohlene Reihenfolge:

```text id="z4b7jx"
New LUMS feature
       │
       ▼
Common implementation
       │
       ▼
Functional tests
       │
       ▼
Theme compatibility
       │
       ▼
Theme-specific refinement
```

So wird verhindert, dass visuelle Anpassungen zu einer Abhängigkeit der Entwicklung von Kernfunktionen werden.

---

## 106. Stabilität der Theme-API

Das Themesystem sollte keine separate API-Ebene einführen, sofern es keinen echten Bedarf dafür gibt.

Themes sollten möglichst denselben Frontend-Anwendungszustand und dieselben API-Mechanismen verwenden wie LUMS.

Dadurch werden reduziert:

* duplizierte Anfrage-Logik
* duplizierte Fehlerbehandlung
* uneinheitliche Annahmen zur Autorisierung
* zusätzlicher Wartungsaufwand
* unnötige Angriffsfläche

Das Themesystem ist deshalb bewusst leichtgewichtig.

---

## 107. Sicherheitsüberprüfung von Themes

Prüfe beim Hinzufügen oder bei wesentlichen Änderungen eines Themes Folgendes:

```text id="3eq4w6"
[ ] No credentials in assets
[ ] No client tokens in assets
[ ] No private keys
[ ] No authentication bypass
[ ] No authorization logic
[ ] No CSRF bypass
[ ] No direct security decisions
[ ] No unintended API endpoints
[ ] No sensitive information in frontend assets
[ ] Decorative scripts remain isolated
```

Diese Überprüfung ist auch dann durchzuführen, wenn eine Änderung rein visuell zu sein scheint.

Frontend-Code ist weiterhin ausführbarer Code.

---

## 108. Barrierefreiheitsprüfung von Themes

Prüfe für jedes Theme Folgendes:

```text id="1y9xw6"
[ ] Text remains readable
[ ] Contrast remains sufficient
[ ] Focus states are visible
[ ] Keyboard navigation works
[ ] Controls remain usable
[ ] Statuses are not color-only
[ ] Reduced motion is respected
[ ] Responsive layout remains usable
[ ] Decorative effects do not obscure information
```

Barrierefreiheit sollte als Bestandteil der Theme-Qualität und nicht als optionale Verbesserung behandelt werden.

---

## 109. Theme-Regressionscheckliste

Vor der Annahme einer Theme-Änderung:

```text id="8j6x4e"
[ ] Standard theme works
[ ] Changed theme works
[ ] Other themes still work
[ ] Theme switching works
[ ] Stored preference works
[ ] Invalid preference falls back safely
[ ] Login works
[ ] Logout works
[ ] Client views work
[ ] Software views work
[ ] Update views work
[ ] Package-management views work
[ ] User-management views work where authorized
[ ] Job information remains readable
[ ] Error messages remain understandable
[ ] RBAC remains unchanged
[ ] Backend behavior remains unchanged
```

Welche Funktionen während des Tests sichtbar sind, hängt von der Rolle des Benutzers ab.

---

## 110. Betriebliche Unabhängigkeit

Das optionale Themesystem ist bewusst vom Betriebslebenszyklus von LUMS unabhängig.

Ein Theme-Wechsel darf Folgendes nicht erfordern:

```text id="b2i1k4"
Agent restart
Watcher restart
Database restart
Client re-registration
Token rotation
Job cancellation
Package-manager changes
Network changes
```

So kann sich die Darstellungsebene unabhängig von der Infrastrukturebene weiterentwickeln.

---

## 111. Unabhängigkeit von der Bereitstellung

Theme-Ressourcen sind Teil des Anwendungs-Frontends von LUMS.

Allgemeine Bereitstellungsverfahren sind in der Hauptdokumentation zu Installation und Administration beschrieben.

Dieses Dokument wiederholt ausdrücklich nicht:

* Docker-Bereitstellungsverfahren
* Befehle zur Container-Härtung
* Nginx-Konfiguration
* Verfahren zur Datenbanksicherung
* Verfahren zur Serverwiederherstellung
* Installationsverfahren für Clients

Diese Themen gehören in die jeweils passende Betriebsdokumentation.

Durch diese Trennung wird verhindert, dass die Theme-Dokumentation bei Änderungen an der Bereitstellungsarchitektur veraltet.

---

## 112. Trennung von Quelle und Laufzeit

Das Themesystem ist als Teil des Anwendungsquellcodes zu verstehen.

Es ist zu unterscheiden zwischen:

```text id="b6q7jv"
Source
   │
   ├── Theme definitions
   ├── CSS
   ├── JavaScript
   └── Assets

Runtime
   │
   ├── Built LUMS image
   └── Running LUMS application
```

Eine Theme-Änderung im Quellcode bedeutet nicht automatisch, dass eine bereits laufende Bereitstellung diese Änderung erhalten hat.

Der normale LUMS-Build- und Bereitstellungsprozess ist weiterhin für die Auslieferung aktualisierter Frontend-Ressourcen zuständig.

---

## 113. Versionierung

Themes müssen keine separate LUMS-Backend-Version einführen.

Ein Theme kann sich als Bestandteil der Frontend-/Anwendungsversion weiterentwickeln.

Werden durch eine Theme-Änderung Kompatibilitätsprobleme verursacht, sollten diese ausdrücklich dokumentiert werden.

Zum Beispiel:

```text id="5y1p8f"
Theme change
     │
     ├── visual-only
     │
     └── compatibility-affecting
```

Die zweite Kategorie erfordert zusätzliche Regressionstests.

---

## 114. Release-Bereitschaft

Prüfe vor einem LUMS-Release mit Theme-Änderungen Folgendes:

```text id="v2h3f7"
Theme rendering
Theme selection
Theme fallback
Accessibility
Reduced motion
Responsive layout
RBAC behavior
API behavior
Security boundaries
Regression tests
Documentation
```

Theme-Änderungen dürfen nicht dazu führen, dass Regressionen in der Kernanwendung verborgen bleiben.

---

## 115. Aktuelle Themes

Die derzeit dokumentierten Theme-Konzepte:

| Kennung | Anzeigename | Konzept |
| ------------- | ---------------- | --------------------------- |
| `standard` | Standard-LUMS | Referenzoberfläche |
| `LUMSStadium` | LUMS-Stadion | Stadion / Ereignis |
| `golf` | Golfclub | Ruhig / Freizeit |
| `nerd` | Nerd-Modus | Technisch / spielerisch |
| `geek` | Geek-Labor | Experimentell / technisch |
| `admin` | Enterprise-Administration | Strukturiert / administrativ |

Diese Themes verwenden dieselbe LUMS-Anwendung und dasselbe Backend.

Es handelt sich um visuelle Varianten, nicht um separate Produkte oder Berechtigungsstufen.

---

## 116. Aktueller Status

Das optionale Themesystem ist eine Erweiterung der LUMS-Frontend-Architektur.

Seine vorgesehenen Eigenschaften:

```text id="2xq1w8"
[✓] Optional
[✓] Client-side presentation
[✓] Common backend
[✓] Common security model
[✓] Common RBAC model
[✓] Standard fallback
[✓] Theme-specific visual identity
[✓] Reduced-motion consideration
[✓] Accessibility consideration
[✓] No theme-based authorization
```

Implementierungsspezifische Details sollten stets mit dem aktuellen Frontend-Quellcode synchronisiert werden.

---

## 117. Zukünftige Erweiterungen

Das Themesystem kann in mehrere Richtungen erweitert werden, ohne die zugrunde liegende Architektur zu verändern.

Mögliche künftige Ergänzungen:

* weitere Themes
* verbesserte Theme-Vorschauen
* detailliertere visuelle Präferenzen
* zusätzliche Barrierefreiheitseinstellungen
* verbessertes responsives Verhalten
* themespezifische Dashboard-Layouts
* weitere optionale Visualisierungen

Solche Erweiterungen sollten weiterhin die Trennung von Darstellung und Anwendungsverhalten einhalten.

---

## 118. Abschließende Architektur

Das vollständige Konzept lässt sich so zusammenfassen:

```text id="x8j7z2"
                    LUMS
                     │
          ┌──────────┴──────────┐
          │                     │
     Application             Theme Layer
          │                     │
          │             ┌───────┼────────┐
          │             │       │        │
          │          Standard Stadium  Golf
          │
          │             Nerd   Geek   Admin
          │
          └──────────────┬──────────────┘
                         │
                         ▼
                  Common Backend
                         │
             ┌───────────┼───────────┐
             │           │           │
          Security      Jobs       Clients
             │           │           │
             └───────────┼───────────┘
                         ▼
                      SQLite
```

Die visuelle Ebene bleibt optional.

Die Anwendungsebene bleibt maßgeblich.

Die Sicherheitsebene bleibt unabhängig.

---

## 119. Abschließendes Prinzip

Das optionale Themesystem soll LUMS persönlicher, ausdrucksstärker und anpassbarer machen, ohne die technische Architektur zu beeinträchtigen.

Der grundlegende Grundsatz bleibt:

> **Ein LUMS · Viele Oberflächen · Dasselbe Backend**

Ein Theme darf die Atmosphäre von LUMS verändern.

Es darf niemals ändern, was LUMS tatsächlich tun darf.
