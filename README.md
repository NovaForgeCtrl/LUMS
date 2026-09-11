# LUMS – Linux Update Management Server

LUMS (**Linux Update Management Server**) ist ein webbasiertes Update-Management-System für Linux-Clients.

Das Projekt ermöglicht die zentrale Erfassung von Client-Informationen, die Anzeige verfügbarer Updates, die Verwaltung von Update-Jobs sowie die Rückmeldung über den tatsächlichen Update-Status.

LUMS wurde als Homelab-Projekt entwickelt und befindet sich aktuell in einem experimentellen Entwicklungsstand.

## Features

* Zentrale Verwaltung mehrerer Linux-Clients
* Automatische Erfassung von:

  * Hostname
  * IP-Adresse
  * Betriebssystem
  * Kernel-Version
  * Architektur
  * Agent-Version
  * verfügbaren Updates
  * installierten Paketen
* Weboberfläche für die Verwaltung der Clients
* Anzeige verfügbarer Updates
* Auswahl einzelner Updates
* Erstellung von Update-Jobs
* Rückmeldung des Update-Ergebnisses
* Erkennung erfolgreich installierter Pakete
* Erkennung fehlgeschlagener Updates
* Timeout-Erkennung
* Erkennung eines erforderlichen Neustarts
* Paketstatus und installierte Versionen
* SQLite-Datenbank für Client- und Jobinformationen
* Aptly als lokales Paket-Repository
* Linux-Agent mit systemd-Unterstützung

---

# Architektur

LUMS besteht aus drei wesentlichen Komponenten:

```text
                     ┌──────────────────────┐
                     │      LUMS Server     │
                     │                      │
                     │ Flask Web/API        │
                     │ SQLite               │
                     │ Aptly Repository     │
                     │ Nginx                │
                     └──────────┬───────────┘
                                │
                 HTTP / REST API│
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
          ▼                     ▼                     ▼
   ┌─────────────┐       ┌─────────────┐       ┌─────────────┐
   │ Linux       │       │ Linux       │       │ Linux       │
   │ Client      │       │ Client      │       │ Client      │
   │             │       │             │       │             │
   │ lums-agent  │       │ lums-agent  │       │ lums-agent  │
   └─────────────┘       └─────────────┘       └─────────────┘
```

## Komponenten

### LUMS Server

Der Server stellt die Weboberfläche und REST-API bereit.

Verwendete Komponenten:

* Ubuntu Server
* Python 3
* Flask
* SQLite
* Nginx
* Aptly

### LUMS Agent

Der Agent läuft auf den verwalteten Linux-Clients.

Der Agent:

1. ermittelt Systeminformationen
2. prüft verfügbare Updates
3. meldet den Zustand an den LUMS-Server
4. fragt nach ausstehenden Update-Jobs
5. führt ausgewählte Updates aus
6. überprüft anschließend den tatsächlichen Paketstatus
7. meldet das Ergebnis an den Server

---

# Voraussetzungen

## Server

Empfohlen:

* Ubuntu Server 24.04 LTS oder neuer
* Python 3
* mindestens 2 GB RAM
* ausreichend Speicherplatz für das lokale Paket-Repository
* Netzwerkzugriff auf die verwalteten Clients

Für ein größeres Paket-Repository sollte entsprechend mehr Speicherplatz eingeplant werden.

## Clients

Unterstützt werden aktuell Linux-Systeme mit:

* `apt`
* `apt-get`
* `dpkg`
* `apt-cache`
* systemd

Getestet wurde LUMS unter anderem mit Ubuntu Linux.

---

# 1. LUMS Server installieren

System aktualisieren:

```bash
sudo apt update
sudo apt upgrade -y
```

Benötigte Pakete installieren:

```bash
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    nginx \
    sqlite3 \
    curl \
    wget \
    git \
    rsync \
    ca-certificates \
    gnupg \
    jq \
    tree \
    htop
```

Projektverzeichnis erstellen:

```bash
sudo mkdir -p /opt/lums-api
sudo mkdir -p /var/lib/lums
```

Quellcode nach `/opt/lums-api` kopieren.

Beispielsweise:

```bash
sudo cp -r server/* /opt/lums-api/
```

---

# 2. Python-Umgebung erstellen

In das Serververzeichnis wechseln:

```bash
cd /opt/lums-api
```

Virtuelle Umgebung erstellen:

```bash
python3 -m venv .venv
```

Aktivieren:

```bash
source .venv/bin/activate
```

Flask installieren:

```bash
pip install flask
```

Die virtuelle Umgebung kann anschließend mit:

```bash
deactivate
```

verlassen werden.

---

# 3. Datenbank initialisieren

Das LUMS-Datenbankverzeichnis erstellen:

```bash
sudo mkdir -p /var/lib/lums
```

Datenbank initialisieren:

```bash
sudo python3 /opt/lums-api/init_db.py
```

Die Datenbank befindet sich anschließend standardmäßig unter:

```text
/var/lib/lums/lums.db
```

> Die Datenbank enthält Laufzeitdaten und gehört nicht in das öffentliche Git-Repository.

---

# 4. LUMS API starten

Zum Testen kann Flask zunächst direkt gestartet werden.

```bash
cd /opt/lums-api
sudo python3 app.py
```

Die API läuft standardmäßig auf:

```text
http://127.0.0.1:5000
```

Die Erreichbarkeit kann beispielsweise mit:

```bash
curl http://127.0.0.1:5000/
```

getestet werden.

---

# 5. Nginx konfigurieren

Nginx kann als Reverse Proxy vor der Flask-Anwendung eingesetzt werden.

Beispiel:

```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Konfiguration testen:

```bash
sudo nginx -t
```

Danach:

```bash
sudo systemctl reload nginx
```

Die Weboberfläche ist anschließend über den Server erreichbar.

---

# 6. Aptly Repository

LUMS kann Aptly als lokales Debian/Ubuntu-Paket-Repository verwenden.

Beispielhafte Verzeichnisstruktur:

```text
/srv/lums/
├── aptly/
├── repository/
├── packages/
├── metadata/
└── logs/
```

Das Repository sollte auf einem ausreichend großen Datenträger liegen.

Beispiel:

```bash
sudo mkdir -p /srv/lums
```

Aptly installieren:

```bash
sudo apt install -y aptly
```

Die konkrete Mirror- und Snapshot-Konfiguration hängt von der verwendeten Ubuntu-Version und der gewünschten Repository-Struktur ab.

---

# 7. LUMS Agent installieren

Auf einem verwalteten Linux-Client:

```bash
sudo mkdir -p /opt/lums-agent
```

Agent kopieren:

```bash
sudo cp agent.py /opt/lums-agent/agent.py
```

Ausführbar machen:

```bash
sudo chmod 755 /opt/lums-agent/agent.py
```

---

# 8. LUMS Agent konfigurieren

Der Agent verwendet die Umgebungsvariable:

```text
LUMS_BASE
```

Dadurch enthält der Quellcode keine feste IP-Adresse des LUMS-Servers.

Beispiel:

```bash
sudo mkdir -p /etc/default
```

Konfigurationsdatei erstellen:

```bash
sudo tee /etc/default/lums-agent > /dev/null <<'EOF'
LUMS_BASE=http://YOUR-LUMS-SERVER:5000
EOF
```

`YOUR-LUMS-SERVER` durch den Hostnamen oder die IP-Adresse des eigenen LUMS-Servers ersetzen.

Beispiel:

```text
LUMS_BASE=http://192.168.1.100:5000
```

> Die tatsächliche Serveradresse gehört zur lokalen Installation und sollte nicht in das öffentliche Repository eingetragen werden.

---

# 9. systemd Service

Die mitgelieferte Service-Datei:

```text
agent/lums-agent.service
```

kann nach:

```text
/etc/systemd/system/lums-agent.service
```

kopiert werden.

Beispiel:

```bash
sudo cp lums-agent.service /etc/systemd/system/lums-agent.service
```

Danach:

```bash
sudo systemctl daemon-reload
```

Agent manuell testen:

```bash
sudo systemctl start lums-agent.service
```

Status prüfen:

```bash
sudo systemctl status lums-agent.service
```

---

# 10. Agent regelmäßig ausführen

Für eine regelmäßige Überprüfung kann systemd einen Timer verwenden.

Beispiel:

```bash
sudo tee /etc/systemd/system/lums-agent.timer > /dev/null <<'EOF'
[Unit]
Description=Run LUMS Agent periodically

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Unit=lums-agent.service

[Install]
WantedBy=timers.target
EOF
```

Timer aktivieren:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lums-agent.timer
```

Status prüfen:

```bash
systemctl status lums-agent.timer
```

Alle Timer anzeigen:

```bash
systemctl list-timers
```

---

# 11. Agent manuell testen

Der Agent kann auch direkt ausgeführt werden:

```bash
sudo /usr/bin/python3 /opt/lums-agent/agent.py
```

Logs können bei einem systemd-Service mit:

```bash
journalctl -u lums-agent.service
```

angezeigt werden.

Live:

```bash
journalctl -u lums-agent.service -f
```

---

# 12. Updates verwalten

Nachdem ein Client seinen Status an den LUMS-Server gemeldet hat, erscheint dieser in der Weboberfläche.

Typischer Ablauf:

```text
Client
  │
  │ Systeminformationen + Updates
  ▼
LUMS Server
  │
  ▼
Weboberfläche
  │
  │ Update auswählen
  ▼
Update Job
  │
  ▼
Client
  │
  │ Paketinstallation
  ▼
Ergebnis
  │
  ▼
LUMS Server
```

Ein Update-Job kann einzelne Pakete enthalten.

Der Agent überprüft nach der Installation den tatsächlichen Paketstatus und meldet das Ergebnis zurück.

Mögliche Ergebnisse sind unter anderem:

```text
success
failed
timeout
partial
```

Außerdem wird geprüft, ob nach dem Update ein Neustart erforderlich ist.

---

# 13. Projektstruktur

```text
LUMS/
├── agent/
│   ├── agent.py
│   ├── lums-agent.env.example
│   └── lums-agent.service
│
├── server/
│   ├── app.py
│   ├── init_db.py
│   ├── static/
│   │   ├── app.js
│   │   ├── client.js
│   │   └── style.css
│   └── templates/
│       ├── client.html
│       └── index.html
│
├── docs/
├── scripts/
├── .gitignore
└── README.md
```

---

# Sicherheit und Datenschutz

LUMS ist aktuell als Homelab- und Entwicklungsprojekt konzipiert.

Das öffentliche Repository enthält **keine**:

* produktiven Datenbanken
* Client-Historien
* privaten IP-Konfigurationen
* Passwörter
* API-Keys
* Tokens
* privaten Schlüssel
* Aptly-Repositories
* Logdateien

Lokale Konfigurationen sollten außerhalb des Git-Repositories gespeichert werden.

Beispielsweise:

```text
/etc/default/lums-agent
```

Die Datei:

```text
agent/lums-agent.env.example
```

dient lediglich als Beispiel und enthält keine produktiven Zugangsdaten.

Vor einer Verwendung in einer produktiven Umgebung sollten insbesondere folgende Punkte geprüft werden:

* Authentifizierung
* Autorisierung
* TLS/HTTPS
* Netzwerksegmentierung
* API-Schutz
* Zugriffsschutz auf die Weboberfläche
* Backup der Datenbank
* Backup des Paket-Repositories
* Logging und Monitoring
* Rollen- und Rechtekonzept

---

# Entwicklungsstatus

LUMS befindet sich derzeit in aktiver Entwicklung.

Der aktuelle Stand ist:

**Experimental / Homelab Project**

Die Software wurde in einer realen Linux-Testumgebung mit mehreren Clients getestet.

Der Schwerpunkt liegt derzeit auf:

* zuverlässiger Update-Erkennung
* zentraler Verwaltung
* Update-Jobs
* Ergebnisprüfung
* Client-Inventarisierung
* Repository-Verwaltung
* stabiler Agent-Kommunikation

APIs, Datenbankstrukturen und Konfigurationsoptionen können sich während der Entwicklung ändern.

---

# Lizenz

LUMS wird unter der **MIT License** veröffentlicht.

Siehe:

```text
LICENSE
```

---

# Haftungsausschluss

LUMS wird ohne Gewähr bereitgestellt.

Der Einsatz von Update-Management-Software kann Systeme verändern und im Fehlerfall deren Verfügbarkeit beeinflussen.

Vor einem produktiven Einsatz sollten Updates zunächst in einer geeigneten Testumgebung geprüft werden.

---

# Projektidee

LUMS entstand als Homelab-Projekt mit dem Ziel, eine einfache Linux-Alternative zu klassischen zentralen Update-Management-Systemen zu entwickeln.

Der Fokus liegt bewusst auf einer überschaubaren Architektur:

```text
Linux Clients
      │
      ▼
   LUMS Agent
      │
      ▼
 REST API
      │
      ├── SQLite
      ├── Web GUI
      └── Aptly
```

Das Projekt soll dabei gleichzeitig als Lern-, Test- und Entwicklungsplattform für Linux-Administration, Python, REST-APIs, Paketverwaltung und Infrastruktur dienen.
