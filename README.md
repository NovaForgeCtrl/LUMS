# LUMS

## Linux Update Management Server

**Linux Update Management without the noise.**

---

# Inhaltsverzeichnis

1. [Über LUMS](#1-über-lums)
2. [Was macht LUMS?](#2-was-macht-lums)
3. [Wie funktioniert LUMS?](#3-wie-funktioniert-lums)
4. [Voraussetzungen](#4-voraussetzungen)
5. [Beispiel-Netzwerk](#5-beispiel-netzwerk)
6. [Vorbereitung des Linux-Servers](#6-vorbereitung-des-linux-servers)
7. [System überprüfen](#7-system-überprüfen)
8. [Benötigte Software installieren](#8-benötigte-software-installieren)
9. [LUMS-Systembenutzer anlegen](#9-lums-systembenutzer-anlegen)
10. [Verzeichnisstruktur erstellen](#10-verzeichnisstruktur-erstellen)
11. [LUMS aus GitHub herunterladen](#11-lums-aus-github-herunterladen)
12. [LUMS installieren](#12-lums-installieren)
13. [Konfiguration und Secret erstellen](#13-konfiguration-und-secret-erstellen)
14. [Datenbank initialisieren](#14-datenbank-initialisieren)
15. [Administratorkonto erstellen](#15-administratorkonto-erstellen)
16. [LUMS als systemd-Dienst einrichten](#16-lums-als-systemd-dienst-einrichten)
17. [LUMS lokal testen](#17-lums-lokal-testen)
18. [HTTPS mit Nginx einrichten](#18-https-mit-nginx-einrichten)
19. [TLS-Zertifikat erstellen](#19-tls-zertifikat-erstellen)
20. [HTTPS testen](#20-https-testen)
21. [Firewall konfigurieren](#21-firewall-konfigurieren)
22. [Weboberfläche aufrufen](#22-weboberfläche-aufrufen)
23. [LUMS-Agent](#23-lums-agent)
24. [Client vorbereiten](#24-client-vorbereiten)
25. [Client beim LUMS-Server registrieren](#25-client-beim-lums-server-registrieren)
26. [Client-Token einrichten](#26-client-token-einrichten)
27. [TLS-Vertrauen auf dem Client einrichten](#27-tls-vertrauen-auf-dem-client-einrichten)
28. [Agent manuell testen](#28-agent-manuell-testen)
29. [Automatische Agent-Ausführung](#29-automatische-agent-ausführung)
30. [Update-Jobs](#30-update-jobs)
31. [Ablauf eines Updates](#31-ablauf-eines-updates)
32. [Update-Ergebnis überprüfen](#32-update-ergebnis-überprüfen)
33. [Client-Status](#33-client-status)
34. [Sicherheit](#34-sicherheit)
35. [Wichtige Dateien](#35-wichtige-dateien)
36. [Wichtige Befehle](#36-wichtige-befehle)
37. [Logs und Fehlersuche](#37-logs-und-fehlersuche)
38. [Häufige Fehler](#38-häufige-fehler)
39. [Backup](#39-backup)
40. [Update von LUMS](#40-update-von-lums)
41. [Deinstallation](#41-deinstallation)
42. [Kompletter Funktionstest](#42-kompletter-funktionstest)
43. [Sicherheits-Checkliste](#43-sicherheits-checkliste)
44. [Projektstruktur](#44-projektstruktur)
45. [Abschluss](#45-abschluss)

---

# 1. Über LUMS

LUMS steht für:

**Linux Update Management Server**

LUMS ist ein kleiner Linux-Update-Management-Server für eine kontrollierte Umgebung.

Der Server sammelt Informationen von Linux-Systemen und kann anschließend Update-Jobs an diese Systeme verteilen.

Ein Client meldet beispielsweise:

* Hostname
* IP-Adresse
* Betriebssystem
* Kernel-Version
* Architektur
* Agent-Version
* installierte Pakete
* verfügbare Updates

Der LUMS-Server speichert diese Informationen in einer SQLite-Datenbank.

Über die Weboberfläche kann anschließend eingesehen werden:

* welche Clients existieren
* ob ein Client erreichbar ist
* wie viele Updates vorhanden sind
* welche Updates verfügbar sind
* welche Update-Jobs ausgeführt wurden
* welche Pakete erfolgreich aktualisiert wurden
* ob ein Neustart erforderlich ist

---

# 2. Was macht LUMS?

LUMS besteht grundsätzlich aus zwei Komponenten.

## 2.1 LUMS Server

Der Server läuft beispielsweise auf:

```text
Ubuntu Server
```

Der Server stellt bereit:

```text
Weboberfläche
API
Datenbank
Authentifizierung
Update-Jobs
Clientverwaltung
Audit-/Sicherheitsfunktionen
HTTPS
```

---

## 2.2 LUMS Agent

Der Agent läuft auf den Linux-Clients.

Der Agent:

1. sammelt Systeminformationen
2. ermittelt verfügbare Updates
3. sendet diese Informationen an LUMS
4. fragt nach einem Update-Job
5. führt den Job aus
6. meldet das Ergebnis
7. sendet anschließend erneut den aktuellen Systemstatus

---

# 3. Wie funktioniert LUMS?

Der grundlegende Ablauf sieht so aus:

```text
                 ┌─────────────────────┐
                 │     LUMS SERVER     │
                 │                     │
                 │ Flask API           │
                 │ Weboberfläche       │
                 │ SQLite              │
                 │ Nginx               │
                 │ HTTPS               │
                 └──────────┬──────────┘
                            │
                            │ HTTPS
                            │ Bearer Token
                            │
                ┌───────────┴───────────┐
                │                       │
        ┌───────▼───────┐       ┌───────▼───────┐
        │ Linux Client  │       │ Linux Client  │
        │               │       │               │
        │ LUMS Agent    │       │ LUMS Agent    │
        │ apt           │       │ apt           │
        │ dpkg          │       │ dpkg          │
        └───────────────┘       └───────────────┘
```

Der Client baut die Verbindung zum Server auf.

Der Server muss daher keine SSH-Verbindung zum Client aufbauen.

Das ist wichtig:

```text
Client → Server
```

und nicht:

```text
Server → Client
```

---

# 4. Voraussetzungen

## 4.1 LUMS Server

Empfohlen:

```text
Ubuntu Server 26.04 LTS
x86_64
```

Für ein kleines Lab reichen beispielsweise:

```text
CPU:    2 Kerne
RAM:    2–4 GB
Disk:   20 GB+
Netz:   1 Gbit/s oder schneller
```

Für größere Installationen sollten die Ressourcen entsprechend angepasst werden.

---

## 4.2 Linux-Client

Der Agent benötigt ein Debian-/Ubuntu-basiertes System mit:

```text
Python 3
APT
dpkg
systemd
```

Der Agent verwendet unter anderem:

```text
apt-get
apt
dpkg-query
systemctl
```

---

## 4.3 Netzwerk

Server und Clients müssen sich gegenseitig erreichen können.

Der Client muss insbesondere HTTPS zum Server erreichen:

```text
TCP 443
```

Der Flask-Port:

```text
TCP 5000
```

sollte **nicht** aus dem Netzwerk erreichbar sein.

LUMS verwendet Flask intern auf:

```text
127.0.0.1:5000
```

Nginx stellt HTTPS nach außen bereit.

---

# 5. Beispiel-Netzwerk

Dieses Beispiel verwendet:

```text
LUMS Server:
192.168.2.134

HTTPS:
https://192.168.2.134

Flask intern:
127.0.0.1:5000
```

Beispiel:

```text
                    LAN
                     │
          ┌──────────┴──────────┐
          │                     │
   192.168.2.134          192.168.2.210
     LUMS Server             Client
          │                     │
          │ HTTPS 443           │
          ◄─────────────────────┤
```

**Hinweis:**

Die IP-Adresse `192.168.2.134` ist nur ein Beispiel aus der Testumgebung.

Bei einer eigenen Installation muss die IP-Adresse des eigenen LUMS-Servers verwendet werden.

---

# 6. Vorbereitung des Linux-Servers

Melde dich auf dem Linux-Server an.

Beispielsweise:

```bash
ssh username@192.168.2.134
```

Oder direkt an der Konsole.

---

# 7. System überprüfen

Zuerst prüfen wir, welches Betriebssystem verwendet wird.

```bash
cat /etc/os-release
```

Bei Ubuntu sollte unter anderem etwas wie folgendes erscheinen:

```text
NAME="Ubuntu"
VERSION="26.04.1 LTS ..."
VERSION_CODENAME=resolute
```

Kernel überprüfen:

```bash
uname -a
```

Architektur:

```bash
uname -m
```

Beispielsweise:

```text
x86_64
```

Python:

```bash
python3 --version
```

Beispielsweise:

```text
Python 3.14.4
```

---

# 8. Benötigte Software installieren

Zuerst Paketquellen aktualisieren:

```bash
sudo apt update
```

Danach benötigte Software installieren:

```bash
sudo apt install -y \
    python3 \
    python3-flask \
    python3-argon2 \
    sqlite3 \
    nginx \
    git \
    openssl \
    curl \
    rsync
```

Installation überprüfen:

```bash
python3 --version
```

```bash
sqlite3 --version
```

```bash
nginx -v
```

```bash
git --version
```

```bash
openssl version
```

---

# 9. LUMS-Systembenutzer anlegen

LUMS soll nicht als `root` laufen.

Deshalb wird ein eigener Systembenutzer erstellt.

```bash
sudo useradd \
    --system \
    --create-home \
    --home-dir /home/lums \
    --shell /usr/sbin/nologin \
    lums
```

Prüfen:

```bash
getent passwd lums
```

Erwartet wird ungefähr:

```text
lums:x:...:...::/home/lums:/usr/sbin/nologin
```

Der Benutzer besitzt keine normale interaktive Shell.

Das bedeutet:

```text
lums
```

ist ein technischer Dienstbenutzer.

---

# 10. Verzeichnisstruktur erstellen

LUMS verwendet folgende Verzeichnisse:

```text
/opt/lums-api
/var/lib/lums
/etc/lums
/etc/lums/tls
```

Erstellen:

```bash
sudo mkdir -p /opt/lums-api
sudo mkdir -p /var/lib/lums
sudo mkdir -p /etc/lums/tls
```

Eigentümer setzen:

```bash
sudo chown lums:lums /opt/lums-api
sudo chown lums:lums /var/lib/lums

sudo chown root:root /etc/lums
sudo chown root:root /etc/lums/tls
```

Berechtigungen setzen:

```bash
sudo chmod 750 /opt/lums-api
sudo chmod 750 /var/lib/lums
sudo chmod 750 /etc/lums
sudo chmod 750 /etc/lums/tls
```

---

# 11. LUMS aus GitHub herunterladen

LUMS befindet sich im GitHub-Repository:

```text
https://github.com/NovaForgeCtrl/LUMS
```

Repository klonen:

```bash
cd /opt
sudo git clone https://github.com/NovaForgeCtrl/LUMS.git lums-public
```

Danach:

```bash
cd /opt/lums-public
```

Git-Status prüfen:

```bash
sudo git status
```

Repository anzeigen:

```bash
sudo git remote -v
```

---

# 12. LUMS installieren

Die Serverdateien befinden sich unter:

```text
/opt/lums-public/server/
```

Diese werden nach:

```text
/opt/lums-api/
```

kopiert.

```bash
sudo rsync -a \
    --delete \
    --exclude='.git/' \
    /opt/lums-public/server/ \
    /opt/lums-api/
```

Danach Eigentümer setzen:

```bash
sudo chown -R lums:lums /opt/lums-api
```

Verzeichnis schützen:

```bash
sudo chmod 750 /opt/lums-api
```

Prüfen:

```bash
ls -la /opt/lums-api
```

Es sollten unter anderem vorhanden sein:

```text
app.py
create_admin.py
init_db.py
security.py
security_migration.py
static/
templates/
```

---

# 13. Konfiguration und Secret erstellen

LUMS benötigt ein geheimes Server-Secret.

Dieses Secret darf nicht veröffentlicht oder in Git eingecheckt werden.

Erstellen:

```bash
sudo sh -c 'umask 077; printf "LUMS_SECRET_KEY=%s\n" "$(openssl rand -hex 64)" > /etc/lums/lums.env'
```

Eigentümer:

```bash
sudo chown root:lums /etc/lums/lums.env
```

Berechtigungen:

```bash
sudo chmod 640 /etc/lums/lums.env
```

Prüfen:

```bash
ls -l /etc/lums/lums.env
```

Erwartet:

```text
-rw-r----- root lums ...
```

Das Secret selbst sollte **nicht** ausgegeben werden.

Stattdessen nur prüfen:

```bash
sudo grep -q '^LUMS_SECRET_KEY=' /etc/lums/lums.env \
    && echo "LUMS_SECRET_KEY vorhanden"
```

---

# 14. Datenbank initialisieren

LUMS verwendet SQLite.

Die Datenbank befindet sich später hier:

```text
/var/lib/lums/lums.db
```

Initialisierung:

```bash
sudo -u lums python3 /opt/lums-api/init_db.py
```

Erwartete Ausgabe:

```text
LUMS-Datenbank aktualisiert: /var/lib/lums/lums.db
```

Berechtigungen setzen:

```bash
sudo chmod 640 /var/lib/lums/lums.db
```

Prüfen:

```bash
ls -l /var/lib/lums/lums.db
```

---

# 15. Administratorkonto erstellen

Jetzt wird die Sicherheitsmigration ausgeführt.

```bash
sudo -u lums python3 /opt/lums-api/security_migration.py
```

Das Programm fragt nach einem Administrator-Benutzer und Passwort.

Beispielsweise:

```text
Username:
Password:
```

Das Passwort wird lokal eingegeben.

**Das Passwort niemals in eine Dokumentation schreiben.**

Nach erfolgreicher Migration sollte unter anderem die Security-Migration abgeschlossen sein.

---

# 16. LUMS als systemd-Dienst einrichten

Damit LUMS automatisch gestartet werden kann, wird ein systemd-Service eingerichtet.

Datei erstellen:

```bash
sudo tee /etc/systemd/system/lums.service > /dev/null <<'EOF'
[Unit]
Description=LUMS API
After=network.target

[Service]
Type=simple
User=lums
Group=lums
WorkingDirectory=/opt/lums-api
EnvironmentFile=/etc/lums/lums.env
ExecStart=/usr/bin/python3 /opt/lums-api/app.py
Restart=on-failure
RestartSec=5

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/var/lib/lums

[Install]
WantedBy=multi-user.target
EOF
```

Danach systemd neu laden:

```bash
sudo systemctl daemon-reload
```

LUMS starten:

```bash
sudo systemctl start lums.service
```

Status:

```bash
sudo systemctl status lums.service
```

Gesucht wird:

```text
Active: active (running)
```

---

# 17. LUMS lokal testen

Flask läuft intern auf:

```text
127.0.0.1:5000
```

Test:

```bash
curl -i http://127.0.0.1:5000/api/health
```

Erwartet:

```text
HTTP/1.1 200 OK
```

und:

```json
{
  "service": "LUMS API",
  "status": "ok"
}
```

Prüfen, ob Port 5000 nur lokal lauscht:

```bash
sudo ss -lntp | grep ':5000'
```

Erwartet:

```text
127.0.0.1:5000
```

Nicht:

```text
0.0.0.0:5000
```

Der Unterschied ist wichtig.

`127.0.0.1` bedeutet:

> Nur der Server selbst kann den Port direkt erreichen.

---

# 18. HTTPS mit Nginx einrichten

LUMS verwendet Nginx als Reverse Proxy.

Der Datenfluss ist:

```text
Browser
   │
   │ HTTPS 443
   ▼
 Nginx
   │
   │ HTTP localhost
   ▼
Flask 127.0.0.1:5000
```

Nginx stellt somit HTTPS bereit.

---

# 19. TLS-Zertifikat erstellen

Für eine interne Lab-Installation kann ein selbstsigniertes Zertifikat verwendet werden.

Zuerst Konfiguration erstellen:

```bash
sudo tee /etc/lums/tls/lums-openssl.cnf > /dev/null <<'EOF'
[req]
default_bits = 4096
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_req

[dn]
C = DE
ST = NRW
L = Essen
O = LUMS
OU = Lab
CN = lums

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = lums
IP.1 = 192.168.2.134
EOF
```

**Wichtig:**

Die IP-Adresse muss angepasst werden.

Wenn der LUMS-Server beispielsweise:

```text
192.168.1.50
```

hat, muss auch:

```text
IP.1 = 192.168.1.50
```

verwendet werden.

Zertifikat erzeugen:

```bash
sudo openssl req \
    -x509 \
    -nodes \
    -newkey rsa:4096 \
    -keyout /etc/lums/tls/lums.key \
    -out /etc/lums/tls/lums.crt \
    -days 825 \
    -config /etc/lums/tls/lums-openssl.cnf
```

Private-Key schützen:

```bash
sudo chmod 600 /etc/lums/tls/lums.key
```

Zertifikat lesbar machen:

```bash
sudo chmod 644 /etc/lums/tls/lums.crt
```

---

# 20. Nginx konfigurieren

Konfiguration erstellen:

```bash
sudo tee /etc/nginx/sites-available/lums > /dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;

    server_name _;

    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;

    server_name _;

    ssl_certificate /etc/lums/tls/lums.crt;
    ssl_certificate_key /etc/lums/tls/lums.key;

    ssl_protocols TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://127.0.0.1:5000;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

Alte Default-Konfiguration deaktivieren:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
```

LUMS aktivieren:

```bash
sudo ln -sf \
    /etc/nginx/sites-available/lums \
    /etc/nginx/sites-enabled/lums
```

Konfiguration prüfen:

```bash
sudo nginx -t
```

Es sollte erscheinen:

```text
syntax is ok
test is successful
```

Nginx neu laden:

```bash
sudo systemctl reload nginx
```

---

# 21. HTTPS testen

Auf dem LUMS-Server:

```bash
curl -k -i https://127.0.0.1/api/health
```

Oder über die Netzwerk-IP:

```bash
curl -k -i https://192.168.2.134/api/health
```

Erwartet:

```text
HTTP/1.1 200 OK
```

und:

```json
{
  "service": "LUMS API",
  "status": "ok"
}
```

Das `-k` wird hier verwendet, weil das Zertifikat selbstsigniert ist.

---

# 22. Weboberfläche aufrufen

Auf einem Computer im gleichen Netzwerk:

```text
https://192.168.2.134/
```

Der Browser wird bei einem selbstsignierten Zertifikat wahrscheinlich eine Warnung anzeigen.

Das ist bei einem selbstsignierten Lab-Zertifikat normal.

Für eine produktive Umgebung sollte eine geeignete interne oder öffentliche PKI verwendet werden.

---

# 23. Firewall konfigurieren

Installieren:

```bash
sudo apt install -y ufw
```

SSH erlauben:

```bash
sudo ufw allow 22/tcp
```

HTTPS erlauben:

```bash
sudo ufw allow 443/tcp
```

HTTP kann optional für die Weiterleitung auf HTTPS geöffnet werden:

```bash
sudo ufw allow 80/tcp
```

Firewall aktivieren:

```bash
sudo ufw enable
```

Status prüfen:

```bash
sudo ufw status verbose
```

Port 5000 darf **nicht** geöffnet werden.

Nicht machen:

```bash
sudo ufw allow 5000/tcp
```

Flask soll ausschließlich lokal erreichbar sein.

---

# 24. LUMS-Agent

Der LUMS-Agent läuft auf einem Linux-Client.

Die Dateien befinden sich im Repository unter:

```text
agent/
```

Wichtige Dateien:

```text
agent.py
lums-agent.env.example
lums-agent.service
lums-agent.timer
```

Der Agent ist für folgende Aufgaben zuständig:

```text
Systeminformationen sammeln
        ↓
Updates ermitteln
        ↓
Report an LUMS senden
        ↓
Nach Update-Job fragen
        ↓
Updates durchführen
        ↓
Ergebnis melden
        ↓
Systemstatus erneut melden
```

---

# 25. Client vorbereiten

Auf dem Linux-Client:

```bash
sudo apt update
```

Benötigte Software:

```bash
sudo apt install -y \
    python3 \
    curl \
    ca-certificates \
    git
```

Repository klonen:

```bash
cd ~
git clone https://github.com/NovaForgeCtrl/LUMS.git lums-public
```

In das Repository wechseln:

```bash
cd ~/lums-public
```

---

# 26. Verbindung zum LUMS-Server testen

Auf dem Client:

```bash
curl -k https://192.168.2.134/api/health
```

Erwartet:

```json
{
  "service": "LUMS API",
  "status": "ok"
}
```

Wenn hier bereits keine Verbindung möglich ist, muss zuerst das Netzwerkproblem gelöst werden.

---

# 27. Client-Token

LUMS verwendet Bearer Tokens zur Authentifizierung von Clients.

Das Token wird nicht als Klartext in der LUMS-Datenbank gespeichert.

Stattdessen wird ein Hash gespeichert.

Der Ablauf ist:

```text
Client
   │
   │ Bearer Token
   ▼
LUMS API
   │
   │ SHA-256
   ▼
Token-Hash
   │
   ▼
Datenbank
```

Das eigentliche Token wird nur auf dem Client gespeichert.

---

# 28. Client beim LUMS-Server registrieren

Ein Client muss zunächst in der LUMS-Datenbank existieren.

Die Datenbank befindet sich auf dem Server:

```text
/var/lib/lums/lums.db
```

Ein Client kann beispielsweise über die LUMS-Verwaltung angelegt werden.

Die Client-ID ist anschließend beispielsweise:

```text
1
```

---

# 29. Client-Token erstellen

Auf dem LUMS-Server kann für einen Client ein Token erzeugt werden.

Dabei wird das Token nur einmal angezeigt.

**Wichtig:**

Das Token ist ein Geheimnis.

Es darf nicht:

* in GitHub gespeichert werden
* in Screenshots auftauchen
* in Dokumentationen stehen
* per Chat weitergegeben werden
* in Logs geschrieben werden

---

# 30. Agent installieren

Auf dem Client:

```bash
sudo mkdir -p /opt/lums-agent
```

Agent kopieren:

```bash
sudo cp ~/lums-public/agent/agent.py /opt/lums-agent/agent.py
```

Berechtigungen:

```bash
sudo chown root:root /opt/lums-agent/agent.py
sudo chmod 755 /opt/lums-agent/agent.py
```

---

# 31. Agent-Konfiguration

Die Konfiguration befindet sich unter:

```text
/etc/default/lums-agent
```

Datei erstellen:

```bash
sudo tee /etc/default/lums-agent > /dev/null <<'EOF'
LUMS_BASE=https://192.168.2.134
LUMS_TOKEN=HIER_DAS_CLIENT_TOKEN_EINTRAGEN
LUMS_CA_FILE=/opt/lums-agent/lums-ca.crt
EOF
```

Danach Token in der Datei ersetzen.

Die Datei darf nur root lesen:

```bash
sudo chown root:root /etc/default/lums-agent
sudo chmod 600 /etc/default/lums-agent
```

---

# 32. TLS-Zertifikat auf dem Client

Da im Lab ein selbstsigniertes Zertifikat verwendet wird, muss der Agent wissen, welchem Zertifikat er vertrauen soll.

Auf dem LUMS-Server befindet sich:

```text
/etc/lums/tls/lums.crt
```

Dieses Zertifikat wird auf den Client kopiert.

Beispielsweise:

```bash
scp username@192.168.2.134:/etc/lums/tls/lums.crt /tmp/lums.crt
```

Danach:

```bash
sudo install \
    -o root \
    -g root \
    -m 644 \
    /tmp/lums.crt \
    /opt/lums-agent/lums-ca.crt
```

---

# 33. TLS-Verbindung testen

Mit Python kann die Verbindung geprüft werden.

Beispiel:

```bash
sudo env \
    LUMS_BASE="https://192.168.2.134" \
    LUMS_CA_FILE="/opt/lums-agent/lums-ca.crt" \
    python3 - <<'PY'
import ssl
import urllib.request

context = ssl.create_default_context(
    cafile="/opt/lums-agent/lums-ca.crt"
)

with urllib.request.urlopen(
    "https://192.168.2.134/api/health",
    context=context
) as response:
    print(response.status)
    print(response.read().decode())
PY
```

Erwartet:

```text
200
{"service":"LUMS API","status":"ok"}
```

---

# 34. Agent-Authentifizierung testen

Der Agent verwendet:

```text
Authorization: Bearer <TOKEN>
```

Der Token wird aus:

```text
/etc/default/lums-agent
```

gelesen.

Test:

```bash
sudo env \
    LUMS_BASE="https://192.168.2.134" \
    LUMS_TOKEN="$(sudo awk -F= '/^LUMS_TOKEN=/{print $2}' /etc/default/lums-agent)" \
    LUMS_CA_FILE="/opt/lums-agent/lums-ca.crt" \
    python3 - <<'PY'
import sys

sys.path.insert(0, "/opt/lums-agent")

import agent

client = agent.get_client()

print("Client-ID:", client["id"])
print("Hostname:", client["hostname"])
print("Enabled:", client["enabled"])
PY
```

Erwartet:

```text
Client-ID: 1
Hostname: test
Enabled: True
```

---

# 35. Agent manuell ausführen

Vor dem automatischen Betrieb sollte der Agent manuell getestet werden.

```bash
sudo env \
    LUMS_BASE="https://192.168.2.134" \
    LUMS_TOKEN="$(sudo awk -F= '/^LUMS_TOKEN=/{print $2}' /etc/default/lums-agent)" \
    LUMS_CA_FILE="/opt/lums-agent/lums-ca.crt" \
    python3 /opt/lums-agent/agent.py
```

Beispielsweise:

```text
=== LUMS Agent ===
Hostname: test
IP: 192.168.2.134
Agent: 1.3.0
Updates: 10
Pakete: 787

Sende Report an LUMS01...
LUMS API: {"status":"received"}
```

Wenn kein Update-Job vorhanden ist:

```text
Kein Update-Job vorhanden.
```

---

# 36. Automatische Agent-Ausführung

Der Agent verwendet systemd.

Service:

```text
lums-agent.service
```

Timer:

```text
lums-agent.timer
```

Service-Datei:

```bash
sudo tee /etc/systemd/system/lums-agent.service > /dev/null <<'EOF'
[Unit]
Description=LUMS Linux Update Management Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/lums-agent/agent.py
EnvironmentFile=-/etc/default/lums-agent

[Install]
WantedBy=multi-user.target
EOF
```

Timer:

```bash
sudo tee /etc/systemd/system/lums-agent.timer > /dev/null <<'EOF'
[Unit]
Description=LUMS Linux Update Management Agent Timer

[Timer]
OnBootSec=2min
OnUnitActiveSec=15min
Unit=lums-agent.service
Persistent=true

[Install]
WantedBy=timers.target
EOF
```

Systemd neu laden:

```bash
sudo systemctl daemon-reload
```

Timer aktivieren:

```bash
sudo systemctl enable --now lums-agent.timer
```

---

# 37. Timer überprüfen

```bash
systemctl status lums-agent.timer
```

Oder:

```bash
systemctl list-timers lums-agent.timer
```

Es sollte ein Zeitplan angezeigt werden.

Der Timer ist konfiguriert auf:

```text
Erster Lauf:
ca. 2 Minuten nach Boot

Danach:
alle 15 Minuten
```

`Persistent=true` sorgt dafür, dass ein verpasster Timer-Lauf nach einem Neustart berücksichtigt werden kann.

---

# 38. Update-Jobs

Ein Update-Job wird auf dem LUMS-Server erstellt.

Ein Job enthält:

```text
Client
Status
Zeitpunkt
Pakete
Zielversionen
Ergebnis
Neustartstatus
```

Beispiel:

```text
Job 3

Client:
test

Pakete:
10

Status:
pending
```

Nach dem Start:

```text
running
```

Nach erfolgreicher Durchführung:

```text
success
```

---

# 39. Ablauf eines Updates

Der komplette Ablauf:

```text
             LUMS
               │
               │ Update Job
               ▼
           Client Agent
               │
               ▼
        Paketliste lesen
               │
               ▼
     apt-get install --only-upgrade
               │
               ▼
        Paket aktualisieren
               │
               ▼
       Ergebnis speichern
               │
               ▼
        Ergebnis an LUMS
               │
               ▼
       neuen Report senden
```

Der Agent verwendet:

```bash
apt-get install --only-upgrade -y <paket>
```

Dadurch werden keine neuen Pakete installiert, die nicht bereits installiert sind.

---

# 40. Beispiel für einen Update-Job

Ein Job kann beispielsweise folgende Pakete enthalten:

```text
libnetplan1
libsqlite3-0
netplan-generator
netplan.io
python3-cryptography
python3-netplan
python3-software-properties
software-properties-common
sqlite3
thermald
```

Der Agent verarbeitet diese Pakete einzeln.

Beispiel:

```text
Update: sqlite3
  $ apt-get install --only-upgrade -y sqlite3
  ✓ sqlite3
```

---

# 41. Update-Ergebnis

Nach Abschluss meldet der Agent:

```text
Erfolgreich: 10
Fehlgeschlagen: 0
Timeout: 0
Neustart erforderlich: False
```

Anschließend wird das Ergebnis an LUMS gesendet.

Beispiel:

```json
{
  "failed_count": 0,
  "job_id": 3,
  "job_status": "success",
  "reboot_required": false,
  "status": "ok",
  "successful_count": 10
}
```

---

# 42. Aktualisierten Systemstatus melden

Nach einem Update sammelt der Agent erneut Informationen.

Beispielsweise:

```text
Erfasse aktuellen Systemstatus nach dem Update...

Updates nach dem Update: 0

Sende aktualisierten Report an LUMS01...
```

Dadurch wird die Liste der verfügbaren Updates aktualisiert.

Beispiel:

```text
Vor Update:
10 Updates

Nach Update:
0 Updates
```

---

# 43. Warum kann die Anzeige zunächst noch alte Updates zeigen?

LUMS speichert die verfügbaren Updates in der Datenbank.

Ein Update-Job ändert zunächst die Job-Daten.

Die aktuelle Update-Liste wird durch einen neuen Client-Report aktualisiert.

Deshalb gilt:

```text
Update erfolgreich
        ↓
Agent sammelt erneut Updates
        ↓
Agent sendet neuen Report
        ↓
LUMS ersetzt alte Update-Liste
        ↓
Anzeige wird aktualisiert
```

---

# 44. Client-Status

LUMS verwendet den Zeitpunkt des letzten Reports.

Aktuelle Logik:

```text
0–120 Sekunden:
online

121–600 Sekunden:
unknown

mehr als 600 Sekunden:
offline
```

Beispiel:

```text
last_seen = gerade eben
→ online
```

Nach mehreren Minuten ohne Report:

```text
→ unknown
```

Nach längerer Zeit:

```text
→ offline
```

---

# 45. Beziehung zwischen Timer und Client-Status

Der Agent läuft aktuell alle:

```text
15 Minuten
```

Der Status `online` gilt jedoch nur für:

```text
120 Sekunden
```

Deshalb kann ein korrekt funktionierender Client zwischen zwei Reports zeitweise als:

```text
unknown
```

oder:

```text
offline
```

erscheinen.

Das ist keine Authentifizierungsstörung.

Für eine zukünftige Produktionslösung könnten beispielsweise folgende Modelle verwendet werden:

```text
kürzeres Report-Intervall
```

oder:

```text
längere Online-Schwelle
```

oder:

```text
separater Heartbeat
```

---

# 46. Sicherheit

LUMS verwendet mehrere Sicherheitsmechanismen.

## 46.1 Client-Authentifizierung

Clients verwenden:

```text
Bearer Token
```

Ohne gültiges Token:

```text
401 Unauthorized
```

---

## 46.2 Client-Isolation

Ein Client darf nicht auf Jobs eines anderen Clients zugreifen.

Beispielsweise:

```text
Client 1 → Job von Client 1
```

ist erlaubt.

Aber:

```text
Client 1 → Job von Client 2
```

wird abgelehnt.

Erwartet:

```text
403 Forbidden
```

---

# 47. Token-Sicherheit

Die Datenbank speichert nicht das Klartext-Token.

Stattdessen:

```text
SHA-256(Token)
```

gespeichert.

Das Token selbst befindet sich auf dem Client:

```text
/etc/default/lums-agent
```

mit:

```text
600
```

Berechtigungen.

---

# 48. Token widerrufen

Wenn ein Client kompromittiert wurde, sollte sein Token widerrufen werden.

Ein widerrufenes Token darf anschließend keine API-Zugriffe mehr durchführen.

Danach kann ein neues Token erzeugt werden.

---

# 49. HTTPS

Die Kommunikation zwischen Agent und Server erfolgt über:

```text
HTTPS
```

Der Agent verwendet das konfigurierte CA-Zertifikat:

```text
/opt/lums-agent/lums-ca.crt
```

Dadurch kann die TLS-Verbindung trotz selbstsigniertem Lab-Zertifikat überprüft werden.

Der Agent verwendet **nicht** einfach:

```text
verify=False
```

Das wäre keine sinnvolle Sicherheitslösung.

---

# 50. Flask-Port

Flask läuft auf:

```text
127.0.0.1:5000
```

Dieser Port darf nicht öffentlich freigegeben werden.

Extern:

```text
HTTPS 443
```

Intern:

```text
127.0.0.1:5000
```

---

# 51. Sicherheits-Header

LUMS setzt unter anderem Sicherheits-Header wie:

```text
X-Content-Type-Options
X-Frame-Options
Referrer-Policy
Permissions-Policy
Content-Security-Policy
```

Die Content Security Policy beschränkt unter anderem:

```text
Scripts
Styles
Images
Frames
Connections
Objects
Forms
```

---

# 52. Wichtige Dateien

## Server

```text
/opt/lums-public/
```

Git-Repository.

```text
/opt/lums-api/
```

Produktive Serverdateien.

```text
/var/lib/lums/lums.db
```

SQLite-Datenbank.

```text
/etc/lums/lums.env
```

Server-Secret.

```text
/etc/lums/tls/
```

TLS-Konfiguration und Zertifikate.

---

## Agent

```text
/opt/lums-agent/agent.py
```

Installierter Agent.

```text
/opt/lums-agent/lums-ca.crt
```

Vertrauenswürdiges LUMS-Zertifikat.

```text
/etc/default/lums-agent
```

Agent-Konfiguration und Token.

```text
/etc/systemd/system/lums-agent.service
```

Agent-Service.

```text
/etc/systemd/system/lums-agent.timer
```

Agent-Timer.

---

# 53. Wichtige systemd-Befehle

LUMS starten:

```bash
sudo systemctl start lums.service
```

LUMS stoppen:

```bash
sudo systemctl stop lums.service
```

LUMS neu starten:

```bash
sudo systemctl restart lums.service
```

Status:

```bash
sudo systemctl status lums.service
```

Automatischen Start aktivieren:

```bash
sudo systemctl enable lums.service
```

---

# 54. Agent-Befehle

Timer starten:

```bash
sudo systemctl start lums-agent.timer
```

Timer stoppen:

```bash
sudo systemctl stop lums-agent.timer
```

Timer aktivieren:

```bash
sudo systemctl enable lums-agent.timer
```

Timer Status:

```bash
systemctl status lums-agent.timer
```

Zeitplan:

```bash
systemctl list-timers lums-agent.timer
```

Agent manuell starten:

```bash
sudo systemctl start lums-agent.service
```

Agent Status:

```bash
sudo systemctl status lums-agent.service
```

---

# 55. Logs anzeigen

LUMS-Logs:

```bash
sudo journalctl -u lums.service
```

Live:

```bash
sudo journalctl -u lums.service -f
```

Letzte 100 Zeilen:

```bash
sudo journalctl -u lums.service -n 100
```

Agent:

```bash
sudo journalctl -u lums-agent.service
```

Live:

```bash
sudo journalctl -u lums-agent.service -f
```

Nginx:

```bash
sudo journalctl -u nginx
```

---

# 56. LUMS-Service startet nicht

Status:

```bash
sudo systemctl status lums.service
```

Danach:

```bash
sudo journalctl -u lums.service -n 100 --no-pager
```

Typische Ursachen:

```text
fehlendes Secret
fehlende Python-Abhängigkeit
falsche Berechtigungen
fehlerhafte Datenbank
Syntaxfehler
```

---

# 57. Flask funktioniert nicht

Test:

```bash
curl -i http://127.0.0.1:5000/api/health
```

Wenn dies nicht funktioniert:

```bash
sudo systemctl status lums.service
```

Port prüfen:

```bash
sudo ss -lntp | grep ':5000'
```

---

# 58. Nginx funktioniert nicht

Konfiguration testen:

```bash
sudo nginx -t
```

Status:

```bash
sudo systemctl status nginx
```

Logs:

```bash
sudo journalctl -u nginx -n 100 --no-pager
```

HTTPS testen:

```bash
curl -k -i https://127.0.0.1/api/health
```

---

# 59. Browser meldet Zertifikatsfehler

Bei einem selbstsignierten Zertifikat ist eine Browserwarnung normal.

Der Browser kennt die eigene CA bzw. das Zertifikat nicht.

Für ein internes Lab kann das Zertifikat manuell als vertrauenswürdig installiert werden.

Für eine echte Produktionsumgebung sollte stattdessen eine geeignete PKI eingesetzt werden.

---

# 60. Agent meldet Zertifikatsfehler

Typischer Fehler:

```text
CERTIFICATE_VERIFY_FAILED
```

Prüfen:

```bash
ls -l /opt/lums-agent/lums-ca.crt
```

Datei muss vorhanden sein.

Konfiguration prüfen:

```bash
sudo grep '^LUMS_CA_FILE=' /etc/default/lums-agent
```

Erwartet:

```text
LUMS_CA_FILE=/opt/lums-agent/lums-ca.crt
```

---

# 61. Agent meldet 401

Wenn der Agent:

```text
401 Unauthorized
```

erhält, sind typische Ursachen:

```text
Token fehlt
Token falsch
Token wurde widerrufen
Client existiert nicht
Client ist deaktiviert
```

Prüfen:

```bash
sudo grep '^LUMS_BASE=' /etc/default/lums-agent
```

Token vorhanden prüfen, ohne es auszugeben:

```bash
sudo grep -q '^LUMS_TOKEN=.' /etc/default/lums-agent \
    && echo "Token vorhanden" \
    || echo "Token fehlt"
```

---

# 62. Agent meldet 403

Ein:

```text
403 Forbidden
```

kann bedeuten, dass der Client versucht, auf einen Job zuzugreifen, der einem anderen Client gehört.

Das ist absichtlich geschützt.

---

# 63. Agent meldet keine Updates

Zuerst direkt mit APT prüfen:

```bash
apt list --upgradable 2>/dev/null
```

Wenn keine Ausgabe vorhanden ist:

```text
Es sind aktuell keine Updates verfügbar.
```

Zusätzlich:

```bash
apt list --upgradable 2>/dev/null | tail -n +2 | wc -l
```

Bei:

```text
0
```

sind keine Updates verfügbar.

---

# 64. Warum zeigt LUMS alte Updates?

Wenn LUMS beispielsweise:

```text
10 Updates
```

anzeigt, APT aber:

```text
0
```

meldet, muss der Agent einen aktuellen Report senden.

Manuell:

```bash
sudo systemctl start lums-agent.service
```

Danach die Weboberfläche aktualisieren.

Der Report synchronisiert:

```text
available_updates
```

mit dem aktuellen Zustand des Clients.

---

# 65. APT und autoremove

LUMS führt nicht automatisch:

```bash
apt autoremove
```

aus.

Das ist bewusst so.

Ein Update-Job aktualisiert vorhandene Pakete.

Es werden nicht automatisch vermeintlich nicht mehr benötigte Pakete entfernt.

---

# 66. Datenbank überprüfen

SQLite-Datenbank:

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db
```

Tabellen anzeigen:

```sql
.tables
```

Beenden:

```sql
.quit
```

---

# 67. Clients anzeigen

Beispielsweise:

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db \
"SELECT id, hostname, ip, os, kernel, architecture, agent_version, last_seen, enabled FROM clients;"
```

---

# 68. Update-Jobs anzeigen

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db \
"SELECT id, client_id, status, created_at, started_at, finished_at, reboot_required FROM update_jobs ORDER BY id;"
```

---

# 69. Update-Pakete anzeigen

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db \
"SELECT id, job_id, package, installed_version, target_version, status FROM update_job_packages ORDER BY id;"
```

---

# 70. Verfügbare Updates anzeigen

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db \
"SELECT client_id, package, installed_version, available_version FROM available_updates ORDER BY client_id, package;"
```

---

# 71. Datenbankintegrität überprüfen

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db \
"PRAGMA integrity_check;"
```

Erwartet:

```text
ok
```

---

# 72. Backup

Die wichtigste Datei ist:

```text
/var/lib/lums/lums.db
```

Ein einfaches Backup:

```bash
sudo cp \
    /var/lib/lums/lums.db \
    /var/lib/lums/lums.db.backup
```

Besser ist ein zeitgestütztes Backup:

```bash
sudo cp \
    /var/lib/lums/lums.db \
    "/var/lib/lums/lums.db.$(date +%Y%m%d-%H%M%S).backup"
```

Auch folgende Dateien müssen bei einer vollständigen Wiederherstellung berücksichtigt werden:

```text
/etc/lums/lums.env
/etc/lums/tls/
```

Insbesondere:

```text
LUMS_SECRET_KEY
```

darf nicht verloren gehen.

---

# 73. LUMS aktualisieren

Repository aktualisieren:

```bash
cd /opt/lums-public
sudo git pull
```

Danach Serverdateien neu deployen:

```bash
sudo rsync -a \
    --delete \
    --exclude='.git/' \
    /opt/lums-public/server/ \
    /opt/lums-api/
```

Eigentümer korrigieren:

```bash
sudo chown -R lums:lums /opt/lums-api
```

Syntax prüfen:

```bash
sudo python3 -m py_compile /opt/lums-api/app.py
```

Service neu starten:

```bash
sudo systemctl restart lums.service
```

Status:

```bash
sudo systemctl status lums.service
```

---

# 74. Agent aktualisieren

Repository aktualisieren:

```bash
cd ~/lums-public
git pull
```

Agent kopieren:

```bash
sudo cp \
    agent/agent.py \
    /opt/lums-agent/agent.py
```

Berechtigungen:

```bash
sudo chown root:root /opt/lums-agent/agent.py
sudo chmod 755 /opt/lums-agent/agent.py
```

Syntax prüfen:

```bash
sudo python3 -m py_compile /opt/lums-agent/agent.py
```

Service-Dateien aktualisieren:

```bash
sudo cp \
    agent/lums-agent.service \
    /etc/systemd/system/lums-agent.service
```

Timer aktualisieren:

```bash
sudo cp \
    agent/lums-agent.timer \
    /etc/systemd/system/lums-agent.timer
```

Systemd neu laden:

```bash
sudo systemctl daemon-reload
```

---

# 75. Git-Sicherheit

Folgende Dateien dürfen niemals in das öffentliche Repository gelangen:

```text
/etc/lums/lums.env
```

und:

```text
/etc/default/lums-agent
```

Insbesondere niemals:

```text
LUMS_SECRET_KEY
```

oder:

```text
LUMS_TOKEN
```

committen.

Vor einem Git-Commit:

```bash
git status
```

prüfen.

Zusätzlich:

```bash
git diff --check
```

---

# 76. Beispiel für sichere Git-Konfiguration

Git-Repository:

```bash
cd /opt/lums-public
```

Status:

```bash
git status
```

Änderungen anzeigen:

```bash
git diff
```

Whitespace-Fehler prüfen:

```bash
git diff --check
```

Danach erst:

```bash
git add .
```

und:

```bash
git commit -m "Update LUMS"
```

Anschließend:

```bash
git push origin main
```

---

# 77. Deinstallation des Agents

Timer stoppen:

```bash
sudo systemctl disable --now lums-agent.timer
```

Service stoppen:

```bash
sudo systemctl stop lums-agent.service
```

Service-Dateien entfernen:

```bash
sudo rm -f /etc/systemd/system/lums-agent.service
sudo rm -f /etc/systemd/system/lums-agent.timer
```

systemd neu laden:

```bash
sudo systemctl daemon-reload
```

Agent entfernen:

```bash
sudo rm -rf /opt/lums-agent
```

Konfiguration entfernen:

```bash
sudo rm -f /etc/default/lums-agent
```

---

# 78. Deinstallation des LUMS-Servers

**Achtung:**

Dieser Abschnitt entfernt die LUMS-Daten.

Vorher unbedingt ein Backup erstellen.

Service stoppen:

```bash
sudo systemctl disable --now lums.service
```

Service-Datei entfernen:

```bash
sudo rm -f /etc/systemd/system/lums.service
```

systemd neu laden:

```bash
sudo systemctl daemon-reload
```

Nginx-Konfiguration entfernen:

```bash
sudo rm -f /etc/nginx/sites-enabled/lums
sudo rm -f /etc/nginx/sites-available/lums
```

Nginx testen:

```bash
sudo nginx -t
```

Nginx neu laden:

```bash
sudo systemctl reload nginx
```

LUMS-Dateien entfernen:

```bash
sudo rm -rf /opt/lums-api
sudo rm -rf /var/lib/lums
sudo rm -rf /etc/lums
```

Danach kann der Systembenutzer entfernt werden:

```bash
sudo userdel lums
```

---

# 79. Kompletter Funktionstest

Nach der Installation sollte folgender Test durchgeführt werden.

## Server

```bash
sudo systemctl is-active lums.service
```

Erwartet:

```text
active
```

---

## Nginx

```bash
sudo systemctl is-active nginx
```

Erwartet:

```text
active
```

---

## HTTPS

```bash
curl -k https://127.0.0.1/api/health
```

Erwartet:

```json
{
  "service": "LUMS API",
  "status": "ok"
}
```

---

## Flask-Port

```bash
sudo ss -lntp | grep ':5000'
```

Erwartet:

```text
127.0.0.1:5000
```

---

## Datenbank

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db \
"PRAGMA integrity_check;"
```

Erwartet:

```text
ok
```

---

## Agent

```bash
sudo systemctl is-active lums-agent.timer
```

Erwartet:

```text
active
```

---

## Agent manuell

```bash
sudo systemctl start lums-agent.service
```

Danach:

```bash
sudo systemctl status lums-agent.service
```

---

# 80. End-to-End-Test

Ein vollständiger Test sieht so aus:

```text
1. Linux Client startet
        ↓
2. systemd Timer wartet
        ↓
3. LUMS Agent startet
        ↓
4. Systeminformationen werden gesammelt
        ↓
5. verfügbare Updates werden ermittelt
        ↓
6. HTTPS-Verbindung zum LUMS Server
        ↓
7. Bearer Token wird verwendet
        ↓
8. Report wird gespeichert
        ↓
9. Agent fragt nach Update-Job
        ↓
10. LUMS liefert Job
        ↓
11. Agent führt apt-get aus
        ↓
12. Ergebnisse werden gespeichert
        ↓
13. Ergebnis wird an LUMS gesendet
        ↓
14. Agent sammelt neuen Systemstatus
        ↓
15. Update-Liste wird aktualisiert
```

---

# 81. Beispiel eines erfolgreichen Tests

Ein erfolgreicher Test kann beispielsweise so aussehen:

```text
=== LUMS Agent ===
Hostname: test
IP: 192.168.2.134
Agent: 1.3.0
Updates: 10
Pakete: 787

Sende Report an LUMS01...
LUMS API: {"status":"received"}


=== LUMS UPDATE JOB ===
Job-ID: 3
Pakete: 10

Update: libnetplan1
  ✓ libnetplan1

Update: libsqlite3-0
  ✓ libsqlite3-0

Update: netplan-generator
  ✓ netplan-generator

Update: netplan.io
  ✓ netplan.io

Update: python3-cryptography
  ✓ python3-cryptography

Update: python3-netplan
  ✓ python3-netplan

Update: python3-software-properties
  ✓ python3-software-properties

Update: software-properties-common
  ✓ software-properties-common

Update: sqlite3
  ✓ sqlite3

Update: thermald
  ✓ thermald

Erfolgreich: 10
Fehlgeschlagen: 0
Timeout: 0
Neustart erforderlich: False
```

Anschließend:

```text
Erfasse aktuellen Systemstatus nach dem Update...

Updates nach dem Update: 0

Sende aktualisierten Report an LUMS01...
```

---

# 82. Sicherheits-Checkliste

Vor einem produktiven Einsatz sollte geprüft werden:

```text
[ ] LUMS läuft nicht als root
[ ] Flask lauscht nur auf 127.0.0.1
[ ] Port 5000 ist nicht aus dem Netzwerk erreichbar
[ ] HTTPS ist aktiviert
[ ] TLS-Zertifikat enthält korrekte SANs
[ ] Client verwendet TLS-Verifikation
[ ] Client verwendet Bearer Token
[ ] Token wird nicht in Git gespeichert
[ ] LUMS_SECRET_KEY wird nicht in Git gespeichert
[ ] /etc/lums/lums.env ist geschützt
[ ] /etc/default/lums-agent ist geschützt
[ ] Datenbank ist nicht öffentlich erreichbar
[ ] Firewall ist aktiv
[ ] SSH ist geschützt
[ ] Datenbank-Backup existiert
[ ] LUMS-Logs sind überprüfbar
[ ] Agent-Timer funktioniert
[ ] Update-Jobs funktionieren
[ ] Client-Isolation funktioniert
[ ] 401 bei fehlender Authentifizierung funktioniert
[ ] 403 bei fremdem Client funktioniert
```

---

# 83. Projektstruktur

Das Repository sieht ungefähr so aus:

```text
LUMS/
│
├── agent/
│   ├── agent.py
│   ├── lums-agent.env.example
│   ├── lums-agent.service
│   └── lums-agent.timer
│
├── server/
│   ├── app.py
│   ├── create_admin.py
│   ├── init_db.py
│   ├── security.py
│   ├── security_migration.py
│   │
│   ├── static/
│   │   ├── client.js
│   │   └── ...
│   │
│   └── templates/
│       ├── client.html
│       └── ...
│
├── README.md
└── ...
```

---

# 84. Produktionspfade

Nach der Installation:

```text
Git Repository
/opt/lums-public

Produktive API
/opt/lums-api

Datenbank
/var/lib/lums/lums.db

Server-Konfiguration
/etc/lums/lums.env

TLS
/etc/lums/tls/

Agent
/opt/lums-agent/agent.py

Agent-Konfiguration
/etc/default/lums-agent

Agent Service
/etc/systemd/system/lums-agent.service

Agent Timer
/etc/systemd/system/lums-agent.timer
```

---

# 85. Architekturübersicht

```text
                         ┌──────────────────────┐
                         │       Browser        │
                         └──────────┬───────────┘
                                    │
                                  HTTPS
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │        Nginx         │
                         │       TCP 443        │
                         └──────────┬───────────┘
                                    │
                            localhost HTTP
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       Flask          │
                         │    127.0.0.1:5000   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       SQLite         │
                         │  /var/lib/lums/...   │
                         └──────────────────────┘


              HTTPS + Bearer Token
                         ▲
                         │
                         │
        ┌────────────────┴────────────────┐
        │                                 │
┌───────┴────────┐               ┌────────┴───────┐
│ Linux Client 1 │               │ Linux Client 2 │
│                │               │                │
│ LUMS Agent     │               │ LUMS Agent     │
│ apt            │               │ apt            │
│ dpkg           │               │ dpkg           │
└────────────────┘               └────────────────┘
```

---

# 86. Grundprinzipien von LUMS

LUMS folgt einigen einfachen Prinzipien:

## Kein unnötiger Netzwerkzugriff

Der Flask-Service ist nur lokal erreichbar.

---

## Authentifizierung

Clients benötigen ein Token.

---

## Verschlüsselte Kommunikation

Client ↔ Server erfolgt über HTTPS.

---

## Geringe Komplexität

LUMS verwendet:

```text
Python
Flask
SQLite
Nginx
systemd
APT
```

Dadurch kann die gesamte Umgebung relativ einfach nachvollzogen werden.

---

## Kein automatisches Aufräumen

LUMS führt nicht automatisch:

```bash
apt autoremove
```

aus.

Updates werden kontrolliert ausgeführt.

---

# 87. Wenn etwas nicht funktioniert

Die wichtigste Regel:

**Nicht sofort alles neu installieren.**

Zuerst die einzelnen Ebenen testen.

## Ebene 1 – Netzwerk

```bash
ping 192.168.2.134
```

## Ebene 2 – HTTPS

```bash
curl -k https://192.168.2.134/api/health
```

## Ebene 3 – Flask

Auf dem Server:

```bash
curl http://127.0.0.1:5000/api/health
```

## Ebene 4 – Nginx

```bash
sudo nginx -t
```

## Ebene 5 – LUMS-Service

```bash
sudo systemctl status lums.service
```

## Ebene 6 – Datenbank

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db \
"PRAGMA integrity_check;"
```

## Ebene 7 – Agent

```bash
sudo systemctl status lums-agent.service
```

## Ebene 8 – Timer

```bash
systemctl list-timers lums-agent.timer
```

## Ebene 9 – Authentifizierung

Token und Client-ID prüfen.

---

# 88. Empfohlene Vorgehensweise bei Problemen

Immer von innen nach außen testen:

```text
SQLite
  ↓
Flask
  ↓
Nginx
  ↓
HTTPS
  ↓
Firewall
  ↓
Netzwerk
  ↓
Agent
  ↓
Authentifizierung
  ↓
Update-Job
```

So lässt sich normalerweise schnell feststellen, an welcher Stelle ein Problem entsteht.

---

# 89. LUMS Installations-Checkliste

## Server

```text
[ ] Ubuntu installiert
[ ] Netzwerk funktioniert
[ ] Python installiert
[ ] Flask installiert
[ ] Argon2 installiert
[ ] SQLite installiert
[ ] Nginx installiert
[ ] Git installiert
[ ] OpenSSL installiert
[ ] LUMS Benutzer erstellt
[ ] Verzeichnisse erstellt
[ ] Repository geklont
[ ] Serverdateien installiert
[ ] Secret erstellt
[ ] Datenbank initialisiert
[ ] Admin erstellt
[ ] systemd Service erstellt
[ ] LUMS gestartet
[ ] Health API funktioniert
[ ] TLS-Zertifikat erstellt
[ ] Nginx konfiguriert
[ ] HTTPS funktioniert
[ ] Firewall konfiguriert
```

---

# 90. Client-Checkliste

```text
[ ] Linux installiert
[ ] Python installiert
[ ] Git installiert
[ ] Repository geklont
[ ] Verbindung zum LUMS Server funktioniert
[ ] Client in LUMS angelegt
[ ] Client-ID vorhanden
[ ] Token erstellt
[ ] /opt/lums-agent erstellt
[ ] agent.py installiert
[ ] /etc/default/lums-agent erstellt
[ ] Token eingetragen
[ ] TLS-CA installiert
[ ] Authentifizierung getestet
[ ] Report getestet
[ ] Agent manuell getestet
[ ] Service installiert
[ ] Timer installiert
[ ] Timer aktiviert
[ ] Update-Job getestet
```

---

# 91. Kurzreferenz

## LUMS Health

```bash
curl -k https://127.0.0.1/api/health
```

## LUMS Status

```bash
sudo systemctl status lums.service
```

## LUMS Logs

```bash
sudo journalctl -u lums.service -f
```

## Nginx testen

```bash
sudo nginx -t
```

## Agent Timer

```bash
systemctl list-timers lums-agent.timer
```

## Agent starten

```bash
sudo systemctl start lums-agent.service
```

## Agent Logs

```bash
sudo journalctl -u lums-agent.service -n 100 --no-pager
```

## Updates des Clients

```bash
apt list --upgradable 2>/dev/null
```

## Datenbankintegrität

```bash
sudo -u lums sqlite3 /var/lib/lums/lums.db \
"PRAGMA integrity_check;"
```

---

# 92. Abschluss

Wenn alle Tests erfolgreich sind, besteht die LUMS-Installation aus:

```text
LUMS Server
    │
    ├── Flask API
    ├── SQLite
    ├── Nginx
    ├── HTTPS
    ├── Authentication
    ├── Client Management
    └── Update Jobs

Linux Client
    │
    ├── LUMS Agent
    ├── APT
    ├── dpkg
    ├── systemd Service
    └── systemd Timer
```

Der typische Arbeitsablauf ist:

```text
Client startet
      ↓
Agent läuft automatisch
      ↓
Systeminformationen werden gesammelt
      ↓
Updates werden erkannt
      ↓
Report wird an LUMS gesendet
      ↓
Administrator sieht den Client
      ↓
Administrator erstellt Update-Job
      ↓
Client fragt Job ab
      ↓
Updates werden installiert
      ↓
Ergebnis wird gemeldet
      ↓
Client erstellt neuen Report
      ↓
Update-Liste ist aktuell
```

Damit ist eine vollständige LUMS-Labumgebung aufgebaut.

---

# LUMS

**Linux Update Management without the noise.**

**Build → Test → Break → Investigate → Understand → Harden → Document**
