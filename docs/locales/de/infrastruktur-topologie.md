# LUMS-Infrastruktur-Topologie

## Zweck

Die authentifizierte Seite `/infrastructure` vereint registrierte
LUMS-Clients und manuell gepflegte Infrastruktur in einer Abhängigkeitsansicht.
Sie ist eine Inventar- und Beziehungskarte, kein System zur automatischen
Netzwerkerkennung oder Konfigurationsverwaltung.

## Datenquellen und Zuständigkeit

- Registrierte LUMS-Clients werden aus der bestehenden Clientregistrierung
  gelesen und automatisch angezeigt, einschließlich gemeldetem Hostnamen,
  IP-Adresse, Betriebssystem und aktiviertem/Melde-Status. Deaktivierte
  Clients bleiben sichtbar, damit bestehende Beziehungen verständlich
  bleiben. Diese Einträge sind auf der Topologieseite schreibgeschützt; verwalte
  Clients über den normalen Clientverwaltungsprozess.
- Server, virtuelle Maschinen, Container, Netzwerkgeräte, Dienste und
  Speicher können manuell mit Hostname, IP-Adresse, Rolle, Standort und
  Notizen eingetragen werden.
- Beziehungen werden manuell gepflegt. Unterstützte Typen sind `depends on`,
  `hosts`, `connects to` und `runs on`.
- Die Seite scannt keine Subnetze, fragt keine Cloud-APIs ab und leitet
  Abhängigkeiten nicht aus Dienst- oder Containerkonfigurationen ab. Halte
  manuell eingetragene Inventardaten und Beziehungen aktuell.

## Zugriffskontrolle und Audit

Benutzer mit `clients.view` können die Topologie anzeigen. Das Erstellen,
Bearbeiten und Löschen manueller Einträge oder Beziehungen ist auf
Administratoren mit der Berechtigung `infrastructure.manage` beschränkt. Die
Anwendung verlangt für Änderungen eine reguläre authentifizierte Sitzung,
CSRF-Schutz und Audit-Protokollierung.

`infrastructure.manage` setzt `users.manage` und `clients.view` voraus und
wird Administratoren durch die Datenbankmigration
`016-infrastructure-topology` erteilt. Beim Entfernen eines manuell
verwalteten Knotens werden auch dessen Beziehungsdatensätze entfernt. Wird ein
Client entfernt, werden Beziehungen gelöscht, die auf diesen Client verweisen.

## Karte lesen

Die Karte ordnet Knoten nach Kategorien an und zeichnet für jede erfasste
Beziehung eine gerichtete Kante. Eine **gemeinsam genutzte Abhängigkeit** ist
ein Knoten, auf den mindestens zwei andere Knoten mit `depends on` verweisen.
Dies ist ein nützlicher Hinweis auf einen möglichen zentralen Ausfallpunkt,
aber keine vollständige Verfügbarkeits- oder Auswirkungsanalyse. Die Karte
berücksichtigt weder Redundanz, Failover und Kapazität noch
Netzwerksegmentierung oder nicht erfasste Abhängigkeiten.

Verwende die Inventar- und Beziehungstabellen für genaue Angaben zu Hostname,
IP-Adresse, Rolle, Standort und Beziehungen. Die Topologie verwendet das
aktuell ausgewählte LUMS-Theme und funktioniert mit der gemeinsamen
einklappbaren Seitenleiste. [Englische Originaldokumentation](../../../LUMS_Infrastructure_Topology.md).
