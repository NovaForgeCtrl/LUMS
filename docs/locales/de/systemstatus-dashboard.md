# LUMS-Systemstatus-Dashboard

## Zweck und Umfang

Das authentifizierte Dashboard unter `/health` bietet Bedienenden einen
schnellen Überblick über ausgewählte LUMS- und Flottenzustände:

- Datenbankstatus gemäß der Bewertung durch die Anwendung;
- Anzahl der Clients insgesamt sowie online, unbekannt und offline;
- aktuelle CPU-, Arbeitsspeicher- und Netzwerk-Telemetrie für einen aktivierten
  Client, sofern Telemetrie installiert ist und Samples vorliegen;
- aktuelle CPU-, Arbeitsspeicher- und Netzwerk-Telemetrie für aktivierte
  Clients, sofern Telemetrie installiert ist und Samples vorliegen;
- Alarmverlauf und erkannte Telemetrieunterbrechungen;
- ob das konfigurierte Sicherungsverzeichnis geprüft werden kann, die neueste
  von der Anwendung erkannte Sicherungsdatei und der letzte erfolgreiche
  Sicherungslauf laut Audit-Log.
- optionale Statuszeilen für Wazuh- und Suricata-systemd-Dienste, sofern
  konfiguriert.

Detaillierte Host- und Netzwerkwerte pro Client, Temperaturen, Dienst- und
Containerzustände sowie Zusammenfassungen von Sicherheitsereignissen befinden
sich auf der separaten Seite `/monitoring`. Die Telemetrie-Unit hat
schreibgeschützten Zugriff auf das Systemjournal, um Ereignisse
zusammenzufassen; sie sendet keine Rohmeldungen aus Protokollen, Benutzernamen
oder Quelladressen. Containerdetails sind nicht verfügbar, sofern das
Dienstkonto der Telemetrie den Laufzeitzugriff nicht ohne zusätzliche
Berechtigungen prüfen kann. Diese Seiten belegen nicht, dass der Host,
Docker-Daemon, Reverse-Proxy, das Netzwerk oder jeder verwaltete Client
fehlerfrei ist. Eine aufgelistete Sicherung beweist nicht, dass sie
wiederherstellbar ist; führe regelmäßig einen kontrollierten
Wiederherstellungstest durch.

## Zugriffskontrolle

Die Seite `/health` erfordert einen angemeldeten Benutzer mit der Berechtigung
`clients.view`. Der Zugriff unterliegt den üblichen Authentifizierungs- und
Autorisierungsprüfungen der Anwendung. Mache das Dashboard nicht öffentlich,
indem du Anmelde- oder Reverse-Proxy-Kontrollen umgehst.

Der separate Endpunkt `GET /api/health` ist eine einfache
Lebendigkeitsprüfung. Eine erfolgreiche Antwort bedeutet, dass die Route
antworten kann; sie ist keine vollständige Bewertung von Datenbank,
Sicherungen oder Clientzustand.

## Interpretation des Clientstatus

Das Dashboard klassifiziert Clients anhand des Zeitpunkts ihrer letzten
Meldung:

| Status | Alter des Zeitstempels |
| --- | --- |
| Online | höchstens 120 Sekunden |
| Unbekannt | mehr als 120 und höchstens 600 Sekunden, fehlender/ungültiger Zeitstempel oder ein Zeitstempel in der Zukunft |
| Offline | mehr als 600 Sekunden |

Diese Schwellenwerte beschreiben, wie aktuell die Meldungen sind, nicht ob ein
Rechner eingeschaltet ist oder alle seine Dienste funktionieren.
Netzwerkverzögerungen, angehaltene Rechner, ein gestoppter Agent oder
Meldeausfälle können das Ergebnis beeinflussen. Betrachte `unknown` als
unzureichende Information und nicht als Beweis für einen Ausfall.

## CPU- und Arbeitsspeichertelemetrie

Telemetrie ist optional und vom Reporting Agent und Execution Watcher getrennt.
Wenn der systemd-Timer aktiviert ist und der Client den Server erreicht,
sendet der Telemetrie-Dienst ungefähr alle fünf Sekunden ein Sample.

Das Dashboard bietet Verlaufszeiträume von 1 Stunde, 24 Stunden und 7 Tagen und
aktualisiert die Flottentelemetrie alle fünf Sekunden. Detaillierte Hostdaten
auf `/monitoring` entsprechen dem zuletzt gemeldeten Snapshot; die Bandbreite
pro Schnittstelle wird aus aufeinanderfolgenden Snapshots berechnet.
Verlaufsabfragen sind auf 1–168 Stunden begrenzt und können auf höchstens 1.000
Punkte heruntergerechnet werden. Samples, die älter als sieben Tage sind,
werden bei der Verarbeitung neuer Telemetrie-Übermittlungen gelöscht; wenn
alle Übermittlungen ausbleiben, ist nicht davon auszugehen, dass die
Aufbewahrungsbereinigung unabhängig davon ausgeführt wird.

Jede Journal-Abfrage auf der Monitoring-Seite ist auf 500 passende Einträge
begrenzt; ein angezeigter Zählerstand von `500+` kann höher sein.
Anmelde-/Abmeldeverläufe sind auf 20 Ereignisse und Systemstartverläufe auf 10
Einträge begrenzt. Das Systemstatus-Dashboard hat ein festes Layout und
verwendet die vorhandenen CPU-/RAM-/Festplattenschwellenwerte pro Benutzer
(Standardwert 90 %). Schwellenwertüberschreitungen und
Telemetrieunterbrechungen werden aus dem aufbewahrten Sample-Verlauf
abgeleitet; Dienstzustandswechsel und neu gemeldete SSH-Fehler werden bis zu
sieben Tage lang als Ereignisse mit Zeitstempel aufgezeichnet.
CSV-/JSON-Exporte enthalten alle Samples des ausgewählten Zeitraums; die
interaktiven Diagramme sind auf 1.000 Punkte begrenzt.

Wazuh- und Suricata-Zeilen sind optional und melden nur systemd-Dienstzustände.
Sie erfordern, dass die entsprechende installierte Unit in
`LUMS_MONITORED_SERVICES` enthalten ist; sie verbinden sich nicht mit den
Wazuh- oder Suricata-APIs und importieren keine Alarmdaten. Der Zeitstempel des
Sicherungslaufs stammt aus dem Audit-Log und ist keine unabhängige
Wiederherstellungsprüfung.

Telemetrie erfordert eine Client-Authentifizierung. Remote-Verbindungen des
Agenten erfordern HTTPS; unverschlüsseltes HTTP ist nur für Loopback-Adressen
zulässig. Konfiguriere eine CA-Datei, wenn der Server eine private
Zertifizierungsstelle verwendet. Einrichtungsdetails findest du unter
[Telemetrie](telemetrie.md) und [Installation und Upgrade](Installation%20und%20Upgrade.md).
[Englische Originaldokumentation](../../../LUMS_Health_Dashboard.md).

## Status des Sicherungsspeichers

Der Sicherungsbereich zeigt, was die Anwendung im konfigurierten
Sicherungsverzeichnis prüfen kann, und die neueste von ihr erkannte
Sicherungsdatei. Er überprüft nicht eigenständig den Inhalt jeder Sicherung,
bestätigt keine Replikation außerhalb des Hosts und beweist nicht, dass eine
Datenbankwiederherstellung erfolgreich ist.

Eine sinnvolle Betriebsroutine:

1. Prüfe, ob das angezeigte Sicherungsdatum für dein Wiederherstellungsziel
   aktuell genug ist.
2. Prüfe Sicherungsauftrag und Anwendungsprotokolle auf Fehler.
3. Vergewissere dich, dass die Sicherung an ein geeignetes, geschütztes Ziel
   kopiert wird.
4. Teste regelmäßig die Wiederherstellung an einem separaten, kontrollierten
   Ort.

Lösche oder überschreibe die aktive Datenbank oder Sicherungsdateien nicht als
Abkürzung zur Fehlerbehebung.

## Empfohlene Prüfungen bei fehlerhaft wirkendem Status

1. Prüfe den LUMS-Container und die aktuellen Protokolle.
2. Prüfe Reverse-Proxy- und TLS-Konfiguration, falls die Seite oder API nicht
   erreichbar ist.
3. Prüfe bei als unbekannt/offline markierten Clients die Timer des Reporting
   Agent und Watcher sowie aktuelle Journal-Einträge.
4. Prüfe bei fehlender Telemetrie `lums-telemetry.timer`,
   `lums-telemetry.service` und die Client-/Serverkonfiguration.
5. Prüfe bei Sicherungswarnungen den konfigurierten Sicherungspfad,
   Dateisystemberechtigungen, verfügbaren Speicherplatz und aktuelle
   Sicherungsprotokolle.
6. Halte den beobachteten Status und die Zeitstempel fest, bevor du Änderungen
   vornimmst.

Diagnosebefehle findest du unter [Fehlerbehebung](Fehlersuche.md), Verfahren
für routinemäßige Wartung und Sicherungen unter [Administration und Backups](Administration%20und%20Backups.md).
