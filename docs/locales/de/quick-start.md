# LUMS-Schnelleinstieg – Deutsch

Dies ist eine kurze Einsteigerhilfe, keine vollständige Übersetzung aller
technischen Handbücher. Die ausführlichen Projektdokumente werden auf Englisch
gepflegt. [Zur Sprachenübersicht](../../README.md).

## Was ist LUMS?

LUMS verwaltet Linux-Rechner zentral. Der Server zeigt Clients, installierte
Software und verfügbare Updates an. Ein Agent auf jedem Client führt
freigegebene Aktionen mit dem Paketmanager des Rechners aus: APT für Debian
und Ubuntu, pacman für Arch Linux. LUMS führt nicht automatisch alle Updates
aus.

## Wenn du nur LUMS verwendest

Öffne die Webadresse, die dir die Administration gegeben hat, und melde dich
mit deinem persönlichen Benutzerkonto an. Die verfügbaren Aktionen hängen von
deinen Berechtigungen ab. Teile weder dein Konto noch ein Client-Token mit
anderen Personen. Wähle die gewünschte Sprache oben rechts auf der
Anmeldeseite; nach der Anmeldung kann LUMS deine Kontoeinstellung speichern.

## Installation und Betrieb

Eine Testinstallation ist kein Produktivserver. Für einen sicheren
Produktivbetrieb brauchst du unter anderem HTTPS, ein geschütztes Secret,
dauerhafte Datenbankablage und geprüfte Backups. Server und Linux-Clients
werden getrennt eingerichtet. Folge der [englischen Installationsanleitung](../../../install.md)
Schritt für Schritt; ersetze Platzhalter wie `LUMS-SERVER` und prüfe jeden
Pfad, bevor du einen Befehl ausführst. Wenn LUMS bereits läuft, verwende die
Upgradeanleitung in der [Administration](../../../administration.md), nicht
die Anleitung zur Erstinstallation.

Bei einem normalen Upgrade darfst du das Docker-Volume `lums-data` nicht
löschen. Es enthält die Datenbank. Bewahre außerdem die vorhandenen
Secret- und Backup-Mounts sowie die Sicherheitseinstellungen des Containers.
Beispielbefehle sind keine universellen Befehle: vergleiche sie immer mit
deinem laufenden Container.

## Erste Prüfungen bei einem Problem

Auf dem Server zeigen diese Befehle den Containerzustand, aktuelle
Anwendungsprotokolle und den Status von Nginx:

```bash
sudo docker ps -a --filter name=lums
sudo docker logs --tail 100 lums
sudo systemctl status nginx --no-pager
sudo nginx -t
```

`sudo` fragt gegebenenfalls nach deinem Linux-Passwort. Diese Prüfungen ändern
die Konfiguration nicht. Lösche keine Datenbank und kein Docker-Volume, starte
den Container nicht privilegiert und deaktiviere keine Sicherheitsoptionen als
ersten Versuch. Teile Protokolle nur, wenn Passwörter, Tokens, Schlüssel und
persönliche Daten entfernt wurden.

## Ausführliche Anleitungen (Englisch)


* [Projektübersicht](Projektüberblick.md)
* [Installation und Upgrade](Installation%20und%20Upgrade.md)
* [Administration und Backups](Administration%und%Backups.md)
* [Fehlersuche](../../../troubleshooting.md)
* [Sicherheitsmodell](../../../security.md)
