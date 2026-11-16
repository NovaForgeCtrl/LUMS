# Herunterladbares Paket mit Aktualisierungswerkzeugen

Nachdem der Workflow `Tests` auf `main` erfolgreich war, erstellt der Workflow
`Updater package` ein Artefakt `lums-update-tools-<commit>.tar.gz` und eine
SHA-256-Prüfsumme. Lade es im Abschnitt **Artifacts** des erfolgreichen
Workflow-Laufs herunter; Build-Artefakte werden 90 Tage aufbewahrt.

Bei Veröffentlichung eines GitHub-Releases führt der Workflow die Testsuite
für den veröffentlichten Tag aus, bevor er das Updater-Archiv und ein
deterministisches Quellarchiv anhängt. Das Quellarchiv enthält seine
SHA-256-Prüfsumme und die Kennung des getesteten Commits; das Update Center
zeigt Releases erst an, wenn alle drei Assets zur Quellcodeprüfung vorliegen.

Das Updater-Tools-Bundle ist ein praktischer Download, kein Debian-Paket. Das
Quellarchiv wird nicht direkt vom Web-Container installiert. Verwende es nicht
zur Aktualisierung einer Produktionsumgebung, bevor ein separat installierter
Host-Updater die Deployment-Prüfungen bestanden und für genau dieses
Deployment sowohl das Datenbank-Backup als auch das Rollback-Verhalten
verifiziert hat.

[Englische Originaldokumentation](../../update-tools-package.md).
