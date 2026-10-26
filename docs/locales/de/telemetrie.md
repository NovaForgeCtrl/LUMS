# LUMS-Telemetrie für CPU, Arbeitsspeicher und Netzwerk

## Überblick

Der optionale LUMS-Telemetrie-Agent erfasst CPU- und Arbeitsspeicherauslastung,
Netzwerkzähler sowie einen begrenzten Host-Snapshot eines verwalteten
Linux-Systems und sendet Messwerte an den LUMS-Server.

Der Server speichert Telemetrie-Samples und stellt eine authentifizierte
Verlaufs-API bereit, die vom Telemetrie-Dashboard des Clients verwendet wird.

Die Telemetrie ist vom vorhandenen LUMS Reporting Agent und Watcher getrennt.
Sie ersetzt keine dieser Komponenten und führt keine Paketaktualisierungen
durch.

## Komponenten

| Komponente | Aufgabe |
| --- | --- |
| `agent/telemetry.py` | Erfasst CPU-, Arbeitsspeicher-, Host-, Netzwerk-, Sensor-, Dienst- und Container-Metriken |
| `agent/lums-telemetry.service` | Führt den Telemetrie-Agenten als eingeschränkten systemd-Dienst aus |
| `agent/lums-telemetry.timer` | Plant wiederkehrende Telemetrie-Erfassungen |
| `server/app.py` | Authentifiziert Übermittlungen, validiert Metriken und speichert Samples |
| `server/static/telemetry.js` | Zeigt die Flottenübersicht, Verlaufsdiagramme und Ringanzeigen an |

## Messwerte

Jedes Sample enthält folgende Pflichtfelder:

- `cpu_percent`: CPU-Auslastung von 0 bis 100.
- `memory_percent`: Arbeitsspeicherauslastung von 0 bis 100.
- `memory_total_bytes`: erkannte Gesamtspeichermenge in Byte.
- `memory_available_bytes`: verfügbarer Arbeitsspeicher in Byte.

Agent-Version 1.1.0 und höher sendet außerdem zwei optionale kumulative Zähler:

- `network_rx_bytes`: seit dem Systemstart empfangene Byte, summiert über alle
  Nicht-Loopback-Schnittstellen.
- `network_tx_bytes`: seit dem Systemstart gesendete Byte, summiert über alle
  Nicht-Loopback-Schnittstellen.

Beide Zähler müssen gemeinsam als nicht negative Ganzzahlen gesendet werden.
Ältere Agenten, die sie weglassen, funktionieren weiterhin; das Dashboard zeigt
dann für diesen Client keine Netzwerkdaten an. Der Server speichert die
Rohzähler und berechnet beim Abruf anhand aufeinanderfolgender Samples die
Byte pro Sekunde. Für das erste Sample, nach einem Zählerreset (zum Beispiel
nach einem Neustart) oder bei einem Abstand von mehr als fünf Minuten zwischen
zwei Samples wird keine Rate angezeigt.

Agent-Version 1.2.0 und höher meldet außerdem einen begrenzten System-Snapshot:

- Load Average, Betriebszeit, Betriebssystem, Kernel und Belegung des
  Root-Dateisystems;
- Verbindungsstatus, Byte-Zähler, Fehler und verworfene Pakete für jede
  Netzwerkschnittstelle;
- konfigurierte DNS-Server sowie bestmögliche Prüfungen der Erreichbarkeit von
  Gateway, DNS und Internet;
- Temperatur- und Lüfterwerte, sofern der Kernel sie bereitstellt;
- ausgewählte systemd-Dienstzustände, Laufzeiten und Neustartzähler sowie
  Docker- und Podman-Containernamen und normalisierte Zustände, sofern lokale
  Werkzeuge und Berechtigungen eine schreibgeschützte Prüfung erlauben;
- Festplattenauslastung bei jedem Telemetrie-Sample für Verlaufsdiagramme und
  die Auswertung von Schwellenwert-Ereignissen.

Agent-Version 1.3.0 und höher meldet außerdem begrenzte Zusammenfassungen
betrieblicher Ereignisse: Anzahl und Zeitstempel fehlgeschlagener
SSH-Anmeldungen, aktuelle Anzahlen von Journal-Warnungen und -Fehlern,
Anmelde-/Abmeldezeitstempel sowie die ersten und letzten Journal-Zeitstempel
aktueller Systemstarts. Rohmeldungen aus dem Journal, Benutzernamen und
Quelladressen werden nicht gesendet. Jede Journal-Abfrage ist auf 500 passende
Einträge begrenzt; das Dashboard kennzeichnet einen Zählerstand von 500 als
`500+`. Die Systemstart- und Anmeldehistorie ist auf 10 Systemstarts und 20
Anmelde-/Abmeldeereignisse begrenzt.

Der Server leitet den Durchsatz pro Schnittstelle aus aufeinanderfolgenden
Samples ab. Details zu Diensten, Containern, Temperaturen, Lüftern und
Ereignissen werden nur als letzter Snapshot gespeichert und nicht in jedem
historischen Sample dupliziert. Optionale Metriken, die das Betriebssystem
nicht bereitstellt oder nicht freigibt, werden als nicht verfügbar angezeigt.
Der Agent startet, stoppt oder verändert keine Dienste oder Container. Der
Agent-Dienst erhält keinen Zugriff auf den Docker-Socket; Containerdetails
bleiben nicht verfügbar, sofern die Laufzeitumgebung dem Dienstkonto nicht
bereits eine Prüfung erlaubt.

Die systemd-Unit für Telemetrie gehört der Gruppe `systemd-journal` an, um
schreibgeschützten Zugriff auf das Journal zu erhalten. Dadurch ist der Zugriff
auf Systemprotokolle möglich, der Agent sendet jedoch nur die oben
beschriebenen begrenzten Zusammenfassungen. Die standardmäßige
Dienst-Allowlist umfasst LUMS-, Docker- und SSH-Units. Überschreibe sie mit
einem durch Kommas getrennten Wert für `LUMS_MONITORED_SERVICES` in der
Umgebungsdatei des Agenten; akzeptiert werden nur gültige `.service`-Unitnamen.

Die Gateway-Erreichbarkeit wird, sofern verfügbar, mit einem einzelnen Ping
geprüft, die DNS-Erreichbarkeit mit einer kurzen `getent`-Abfrage und die
Internet-Erreichbarkeit mit einem kurzen TCP-Verbindungsversuch zu
`1.1.1.1:443`. Diese Prüfungen sind lediglich Indikatoren und können eher
Firewall-Regeln als einen Ausfall widerspiegeln.

Der Server weist dem Sample den Zeitstempel zu und lehnt ungültige Nutzdaten ab.

Führe nach der Aktualisierung des Servers die Datenbankmigration einmalig aus
(`python3 server/security_migration.py`), damit die Netzwerksäulen, die Tabelle
für den letzten Systemzustand und der Ereignisverlauf vorhanden sind.
Aktualisiere den Agenten auf jedem Client, damit die neuen Metriken gemeldet
werden. Um den LUMS-Server selbst zu überwachen, registriere ihn als Client und
installiere und konfiguriere den Telemetrie-Agenten auch auf diesem Host.

## Sicherheit und Datenschutz

Der Telemetrie-Endpunkt erfordert eine Client-Authentifizierung mit dem
konfigurierten LUMS-Client-Token.

Bei Verbindungen zu einem Remote-Server sendet der Agent Anfragen über HTTPS.
Unverschlüsseltes HTTP ist nur für `localhost`, `127.0.0.1` und `::1` zulässig.
Verbindungen zu Remote-Servern erfordern HTTPS. Optional kann eine CA-Datei für
die Zertifikatsprüfung konfiguriert werden.

Der Agent nimmt das Client-Token weder in die JSON-Nutzdaten auf noch
protokolliert er es. Der systemd-Dienst verwendet eine eingeschränkte
Ausführungsumgebung und benötigt keine Root-Rechte, um die dokumentierten
Metriken zu erfassen.

Die Telemetrie enthält Systemressourcen und betriebliche Metadaten, keine
Paketaktualisierungen oder beliebige Befehlsausgaben. Schnittstellenadressen,
DNS-Server, Dienstnamen und Containernamen können vertrauliche
Infrastrukturdaten sein; der Zugriff auf Dashboard und API ist weiterhin durch
die Berechtigung `clients.view` geschützt.

## Datenaufbewahrung

Der Server entfernt Telemetrie-Samples, die älter als sieben Tage sind, wenn er
neue Telemetrie-Übermittlungen verarbeitet.

Der authentifizierte Verlaufsendpunkt akzeptiert einen Zeitraum von 1 bis 168
Stunden. Für den Zugriff ist die entsprechende Berechtigung zum Anzeigen von
Clients erforderlich. Große Ergebnismengen können auf maximal 1.000 Samples
heruntergerechnet werden.

Das `/health`-Dashboard bietet Verlaufszeiträume von 1 Stunde, 24 Stunden und
7 Tagen und aktualisiert die angezeigten Daten alle fünf Sekunden. Es zeigt
CPU-, Arbeitsspeicher- und Festplattenauslastung sowie den aggregierten
Netzwerkverlauf und für den ausgewählten Client aktuelle Details zu
Festplatten, Load, Betriebszeit, Kernel, Betriebssystem, Schnittstellen,
Verbindungen, Sensoren, Diensten und Containern. Außerdem zeigt es eine nach
Status, veralteter Telemetrie oder hoher Last filterbare, durchsuchbare und
sortierbare Flottenübersicht sowie Details pro Client. CPU und Arbeitsspeicher
können als Linien- oder Flächendiagramm oder als Ringanzeige des aktuellen
Werts dargestellt werden; die gewählte Ansicht wird im Browser gespeichert.
Der Netzwerkverkehr wird als Download- und Upload-Rate angezeigt. Telemetrie,
die älter als zwei Minuten ist, wird als veraltet markiert. Die
Flottenübersicht verwendet den Endpunkt `/api/telemetry/overview`, für den die
Berechtigung zum Anzeigen von Clients erforderlich ist. Verlaufsanfragen sind
auf 1–168 Stunden begrenzt und können auf maximal 1.000 Samples
heruntergerechnet werden. Der systemd-Timer ist so konfiguriert, dass er den
Einmal-Agenten alle fünf Sekunden ausführt; die tatsächliche Sample-Häufigkeit
hängt von der Dienstausführung und der Netzwerkverfügbarkeit ab. Das Dashboard
zeigt außerdem aktuelle SSH-Fehler, Journal-Warnungs-/Fehlerzähler,
Anmelde-/Abmelde- und Systemstartverlauf an. Schwellenwertwarnungen verwenden
die konfigurierbaren CPU-, RAM- und Festplattenlimits des angemeldeten
Benutzers. Journal-Zähler umfassen höchstens 500 passende Einträge pro Abfrage.
Der letzte erfolgreiche Sicherungslauf wird aus dem Audit-Log des Servers
ausgelesen; dies ist kein Wiederherstellungstest.

Schwellenwertüberschreitungen und Telemetrielücken von mehr als zwei Minuten
werden im Ereignisverlauf angezeigt. Schwellenwertwarnungen werden anhand
aufbewahrter Samples und der Schwellenwerte des angemeldeten Benutzers
abgeleitet; Dienstzustandswechsel und neue Zeitstempel fehlgeschlagener
SSH-Anmeldungen werden bei der Verarbeitung aufgezeichnet. Ereignisse werden
bis zu sieben Tage aufbewahrt; der Ereignisendpunkt liefert höchstens 500
Einträge.

Für den ausgewählten Client und Zeitraum sind CSV- und JSON-Exporte verfügbar.
Verlaufsdownloads enthalten alle aufbewahrten Samples dieses Zeitraums; die
Diagramme bleiben auf maximal 1.000 Punkte heruntergerechnet. Für Exporte ist
`clients.view` erforderlich; der Browser speichert sie nicht im Cache.

Wazuh und Suricata können als optionale Statuszeilen im Dashboard angezeigt
werden. Diese Zeilen zeigen ausschließlich den konfigurierten systemd-
Dienstzustand an; LUMS verbindet sich weder mit ihren APIs noch sammelt es
deren Warnmeldungen. Damit ein Dienst gemeldet wird, muss seine installierte
Unit (zum Beispiel `wazuh-agent.service`, `wazuh-manager.service` oder
`suricata.service`) in der Allowlist `LUMS_MONITORED_SERVICES` des Agenten
enthalten sein. LUMS benötigt und speichert keine Integrationsanmeldedaten.

## Konfiguration

Der Telemetrie-Agent verwendet die Umgebungsvariablen `LUMS_BASE`,
`LUMS_TOKEN` und optional `LUMS_CA_FILE`. Verbindungen zu Remote-Servern
erfordern HTTPS. Installations- und Konfigurationsanweisungen findest du in
[Installation und Upgrade](Installation%20und%20Upgrade.md). [Englische
Originaldokumentation](../../../telemetry.md).

## Installation und Betrieb

Der Telemetrie-Dienst ist vom normalen LUMS-Client getrennt. Aktualisiere unter
Debian zunächst den LUMS-Repository-Checkout auf dem Client und führe im
Stammverzeichnis `sudo bash scripts/install-telemetry-agent.sh` aus. Das
Installationsprogramm prüft, ob `/etc/default/lums-agent` `LUMS_BASE` und
`LUMS_TOKEN` definiert, installiert den aktuellen Collector und die
systemd-Units, aktiviert den Timer und sendet ein Test-Sample. Das Token wird
niemals ausgegeben.

Prüfe Timer und Dienst mit `systemctl status lums-telemetry.timer` und
`systemctl status lums-telemetry.service`. Sieh dir die aktuellen
Dienstprotokolle mit `journalctl -u lums-telemetry.service -n 30 --no-pager`
an. Ein inaktiver Einmal-Dienst zwischen geplanten Ausführungen ist nicht
zwangsläufig ein Fehler; prüfe auch den Timer und die aktuellen Protokolle.

Die Seite `/monitoring` unterscheidet zwischen fehlenden Samples, einfacher
Telemetrie ohne detaillierte Snapshots und einem veralteten Snapshot und zeigt
diese clientseitigen Prüfungen an. Füge das Token bei der Fehlersuche nicht in
Nachrichten ein und gib es nicht weiter.

## Fehlerbehebung

- **Keine Samples sichtbar:** Prüfe Server-URL, Client-Token und Authentifizierung.
- **TLS-Fehler:** Prüfe das Serverzertifikat und die konfigurierte CA-Datei.
- **Dienstfehler:** Prüfe das Journal des Dienstes.
- **Verlauf fehlt:** Prüfe die Berechtigung zum Anzeigen von Clients und den
  angeforderten Zeitraum (1–168 Stunden).

Informationen zu Statusschwellenwerten des Dashboards und den Grenzen seiner
Sicherungsanzeige findest du im [Systemstatus-Dashboard](systemstatus-dashboard.md).
Allgemeine Hinweise stehen unter [Installation und Upgrade](Installation%20und%20Upgrade.md)
und [Fehlerbehebung](Fehlersuche.md).
