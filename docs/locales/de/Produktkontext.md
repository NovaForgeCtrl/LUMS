# LUMS-Produktkontext

## Plattform

Webanwendung

## Benutzer

Linux-Systemadministratoren und IT-Teams, die mehrere Linux-Systeme zentral verwalten und aktuell halten. Das Produkt soll sich auch für einzelne Administratoren, kleine IT-Teams und geeignete Managed-Service-Umgebungen eignen.

## Produktzweck

LUMS bietet eine zentrale Übersicht über verwaltete Clients, installierte Software, verfügbare Updates und die Ausführung von Update-Aufträgen. Administratoren können damit Arbeiten gezielt anstoßen und Ergebnisse überprüfen, statt Updates blind auf allen Systemen einzuspielen.

## Betriebsumgebung

Administratoren verwenden LUMS im täglichen Betrieb, um den Zustand der Systemflotte, Telemetriedaten, Software und Updates zu prüfen, gezielte Update-Aufträge zu starten, den Ausführungsverlauf einzusehen und Benutzerzugriffe, Audit-Datensätze sowie Datenbanksicherungen zu verwalten. Die Infrastruktur-Topologie kann registrierte LUMS-Clients mit manuell gepflegten Systemen und Beziehungen kombinieren.

## Funktionen und Einschränkungen

- Rollen- und berechtigungsbasierte Zugriffskontrollen, Audit-Protokollierung, Datenbanksicherungen, Paketübersicht und Update-Aufträge für Clients gehören zu den zentralen Betriebsfunktionen.
- Systemaktualisierungen müssen kontrolliert und nachvollziehbar sein und Fehler ehrlich melden. Ein Update darf nur dann als erfolgreich dargestellt werden, wenn seine Prüfungen bestanden wurden.
- Registrierte Clients und ihre gemeldeten Daten bilden die verfügbare Quelle für automatisch importierte Infrastrukturinventardaten. Weitere Infrastruktur und Beziehungen müssen ausdrücklich manuell eingetragen werden, sofern keine zukünftige Integration bestätigt ist.
- Änderungen am Infrastrukturinventar sind Administratoren vorbehalten.
- Eine automatische Erkennung beliebiger virtueller Maschinen, Container, Netzwerkgeräte oder Abhängigkeiten darf nicht behauptet werden.

## Markenverpflichtungen

- Den Namen LUMS und das vorhandene Logo beibehalten.
- Der Benutzer bezeichnet das Stadion-Theme ausdrücklich als „LUMS-Stadion“ und hat darum gebeten, dessen vorhandenes Stadion-Hintergrundbild auf dem Systemstatus-Dashboard und in der Live-Überwachung zu verwenden.

## Vorliegende Belege

- Vorhandene Produktoberfläche und Theme-Ressourcen: `server/static/style.css`, `server/static/images/LUMS_Logo.jpg` und `server/static/images/lumsstadium.jpg`.
- Vorhandene Implementierungen für registrierte Clients, Telemetrie, Update-Aufträge, RBAC, Audit-Protokollierung und Backups befinden sich im Paket `server/`.
- Es liegen keine verifizierten Kundenaussagen, Produkt-Benchmarks oder Integrationen zur automatischen Infrastrukturerkennung vor.

## Produktprinzipien

- Administratoren behalten die Kontrolle über Systemänderungen.
- Betriebsstatus und Update-Ergebnisse müssen überprüfbar sein.
- Zugriffsregeln werden serverseitig durchgesetzt, nicht nur in der Oberfläche.
- Gemeldete Fakten von Clients sind von manuell gepflegtem Inventar zu unterscheiden.
