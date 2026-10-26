# Przewodnik instalacji LUMS

## Serwer zarządzania aktualizacjami Linuksa

**Projekt:** LUMS
**Slogan:** Zarządzanie aktualizacjami Linuksa bez zbędnego szumu.
**Repozytorium:** `NovaForgeCtrl/LUMS`

---

## Pierwsze kroki: Zrozum instalację, zanim zaczniesz

Ten przewodnik obejmuje kompletną instalację serwera, w tym zaawansowane procedury konserwacji i weryfikacji. To **nie** jest pojedynczy skrypt do uruchomienia bez przeglądu: nazwa serwera, certyfikat TLS, plik sekretu, miejsce docelowe kopii zapasowych, sieć i baza danych różnią się między instalacjami.

### Co zostanie zainstalowane?

* **Serwer LUMS:** interfejs webowy i API, działające w kontenerze Docker.
* **Nginx:** przyjmuje zewnętrzne połączenia HTTPS i przekazuje je lokalnie do kontenera.
* **Wolumen danych:** zawiera bazę danych SQLite. Ten wolumen musi przetrwać aktualizacje i nigdy nie może zostać usunięty podczas normalnego zastępowania kontenera.
* **Plik sekretu:** chroni między innymi sesje aplikacji. Nigdy nie umieszczaj go w repozytorium Git, obrazie Docker ani wiadomości na czacie.
* **LUMS Agent i Watcher:** instalowane oddzielnie na zarządzanych klientach Linuksa. Sam działający serwer nie aktualizuje żadnych klientów.

| Termin | Znaczenie |
| --- | --- |
| Terminal / powłoka | Okno tekstowe, w którym wprowadzasz polecenia Linuksa. |
| `sudo` | Uruchamia następujące polecenie z uprawnieniami administratora. Linux może poprosić o hasło. |
| Host | Komputer z Linuksem, na którym działają Docker i serwer LUMS. |
| Kontener | Izolowany proces uruchamiający aplikację webową LUMS. |
| Obraz | Przygotowany szablon, którego Docker używa do uruchomienia kontenera. |
| Wolumen | Trwałe przechowywanie Docker, które pozostaje po zastąpieniu kontenera. |
| Symbol zastępczy | Tekst taki jak `LUMS-SERVER`, który należy zastąpić rzeczywistą wartością. |

### Uruchom tylko testy (to nie instaluje serwera)

Te kroki są odpowiednie dla Debian 13, aby pobrać źródła i uruchomić testy lokalnie. **Nie** tworzą serwera produkcyjnego dostępnego przez sieć i nie instalują agenta na innym komputerze. `sudo` jest potrzebne tylko do zainstalowania pakietów Debiana.

```bash
sudo apt update
sudo apt install -y git python3 python3-venv
git clone https://github.com/NovaForgeCtrl/LUMS.git ~/LUMS
cd ~/LUMS
python3 -m venv .venv-test
./.venv-test/bin/python -m pip install -r server/requirements.txt -r requirements-dev.txt
./.venv-test/bin/pytest -q
```

`apt update` odświeża listy pakietów; nie aktualizuje całego zainstalowanego oprogramowania. Środowisko wirtualne Pythona `.venv-test` utrzymuje zależności testowe oddzielnie od reszty systemu. Pomyślne uruchomienie testów kończy się kodem wyjścia `0`; liczba testów może zmieniać się w miarę rozwoju projektu. Jeśli utworzenie środowiska się nie powiedzie, sprawdź, czy zainstalowano `python3-venv`. Jeśli test się nie powiedzie, zapisz pełny błąd i przeczytaj [przewodnik rozwiązywania problemów](Rozwiązywanie problemów.md); nie usuwaj danych produkcyjnych.

W przypadku rzeczywistej instalacji kontynuuj z numerowanymi sekcjami i najpierw przeczytaj instrukcje dotyczące bezpieczeństwa i kopii zapasowych. Jeśli LUMS już działa, użyj procedury aktualizacji w [`administration.md`](Administracja i kopie zapasowe.md), a nie procedury pierwszej instalacji.

---

# 1. Przegląd

LUMS to scentralizowana platforma zarządzania aktualizacjami Linuksa do kontrolowanej dystrybucji aktualizacji, raportowania klientów, zarządzania pakietami, wykonywania zadań aktualizacji, walidacji wyników i audytowalnej administracji.

Obecna architektura oddziela serwer zarządzania od zarządzanych klientów Linuksa.

Serwer zapewnia:

* Administrację opartą na sieci web
* Zarządzanie klientami
* Uwierzytelnianie klientów
* Inwentarz pakietów
* Raportowanie dostępnych aktualizacji
* Wyszukiwanie pakietów
* Instalację i usuwanie pakietów
* Zarządzanie zadaniami aktualizacji
* Walidację wyników zadań
* Historię aktualizacji
* Kontrolę dostępu opartą na rolach
* Rejestrowanie audytu
* Trwały stan oparty na SQLite

Klienci Linuksa zapewniają:

* Informacje o systemie
* Inwentarz zainstalowanych pakietów
* Wykrywanie dostępnych aktualizacji
* Operacje na pakietach
* Wykonywanie zadań aktualizacji
* Wykrywanie stanu bezczynności
* Punkty kontrolne i wznawianie zadań
* Wykrywanie restartu
* Raportowanie wyników

Obecna implementacja obsługuje:

```text
Debian / Ubuntu
    └── APT / dpkg

Arch Linux
    └── pacman
```

---

# 2. Architektura

Architektura produkcyjna jest następująca:

```text
                         LUMS Server
                              │
                              │ HTTPS :443
                              ▼
                       ┌──────────────┐
                       │    Nginx     │
                       │  TLS / Proxy │
                       └──────┬───────┘
                              │
                              │ HTTP
                              ▼
                       127.0.0.1:5050
                              │
                              ▼
                    ┌───────────────────┐
                    │   Docker: lums    │
                    │                   │
                    │   Gunicorn        │
                    │   Flask :5000     │
                    │   SQLite          │
                    └─────────┬─────────┘
                              │
                              ▼
                         lums-data
                              │
                              ▼
                   /var/lib/lums/lums.db


        Linux Client
              │
              │ HTTPS + Bearer Token
              ▼
         LUMS API
              │
              ├── Report
              ├── Package Search
              ├── Job Retrieval
              └── Job Result
```

Aplikacja LUMS **nie jest przeznaczona do bezpośredniego udostępniania w sieci**.

Kontener aplikacji jest powiązany z:

```text
127.0.0.1:5050 → container:5000
```

Nginx jest zewnętrznym punktem wejścia HTTPS.

Port `5000` nie jest publikowany bezpośrednio.

Port `5050` musi pozostać ograniczony wyłącznie do localhost.

---

# 3. Komponenty aplikacji

Kompletna instalacja LUMS składa się z kilku komponentów.

## 3.1 Serwer LUMS

Serwer zawiera:

```text
Flask
Gunicorn
SQLite
Web UI
REST API
Authentication
RBAC
Audit logging
Job management
Package management
```

Aplikacja działa wewnątrz kontenera Docker:

```text
lums
```

Trwała baza danych jest przechowywana poza zapisywalnym systemem plików aplikacji kontenera:

```text
lums-data:/var/lib/lums/lums.db
```

---

## 3.2 Nginx

Nginx zapewnia:

```text
HTTPS termination
TLS certificate handling
HTTP → HTTPS redirect
Reverse proxy
External network entry point
```

Zamierzona ścieżka żądania to:

```text
Browser
   │
   │ HTTPS
   ▼
Nginx
   │
   │ localhost HTTP
   ▼
127.0.0.1:5050
   │
   ▼
LUMS
```

Aplikacja Flask/Gunicorn nie powinna być bezpośrednio udostępniana w sieci LAN.

---

## 3.3 Agent Linuksa

Agent LUMS działa na każdym zarządzanym kliencie Linuksa.

Obecna wersja agenta:

```text
1.7.0
```

Agent odpowiada za:

```text
System information
Installed packages
Available updates
Client reporting
Job retrieval
Job claiming
Package operations
Result reporting
Reboot detection
```

Agent komunikuje się z serwerem LUMS przez HTTPS i token Bearer specyficzny dla klienta.

---

## 3.4 Watcher wykonania

Watcher wykonania odpowiada za kontrolowane wykonywanie zadań aktualizacji.

Obecna wersja Watchera:

```text
1.2.1
```

Watcher obsługuje:

```text
Pending-job detection
Idle-state checks
Atomic job claiming
Update execution
Checkpoint handling
Interrupted-job recovery
Result processing
```

Watcher jest celowo oddzielony od zwykłego raportowania klientów.

---

# 4. Model bezpieczeństwa

Instalacja musi zachować podstawę bezpieczeństwa LUMS.

Serwer produkcyjny używa:

```text
HTTPS
Bearer-token client authentication
Role-based web authorization
CSRF protection
Audit logging
Read-only container root filesystem
Dropped Linux capabilities
no-new-privileges
Non-root application user
Localhost-only application port
Persistent Docker volume
Read-only secret mount
```

Kontener Docker działa jako nieuprzywilejowany użytkownik:

```text
lums
```

z UID:

```text
10001
```

Kontener nie może działać w trybie uprzywilejowanym.

System plików główny musi pozostać tylko do odczytu.

Aplikacja nie może wymagać dostępu do zapisu w swoim katalogu aplikacji.

Trwałe dane aplikacji są przechowywane w dedykowanym wolumenie Docker.

---

# 5. Obecny model RBAC

LUMS obecnie oferuje trzy role webowe:

```text
administrator
operator
viewer
```

## Administrator

Administratorzy mogą wykonywać operacje administracyjne, w tym:

```text
View clients
View installed software
View available updates
Create and execute update jobs
View update history
Use package management
Use system maintenance
Create and disable clients
Rotate client tokens
Manage users
Manage roles
```

---

## Operator

Operatorzy mogą wykonywać zarządzanie operacyjne:

```text
View clients
View installed software
View available updates
Create and execute update jobs
View update history
Use package management
Use system maintenance
```

Operatorzy nie mają dostępu do:

```text
User management
Role management
Client creation/disabling
Client-token rotation
```

---

## Viewer

Viewerzy mają celowo ograniczony dostęp.

Viewer może uzyskać dostęp do:

```text
Clients
Installed software
```

Następujące obszary zarządzania są ukryte w interfejsie Viewera i chronione po stronie serwera:

```text
Available updates
Update Jobs
Update History
Package Management
System Maintenance
```

Dlatego ukrycie w UI nie jest granicą bezpieczeństwa.

Autoryzacja po stronie serwera pozostaje obowiązkowa.

---

# 6. Wymagania instalacyjne

## 6.1 Serwer LUMS

Obecne wdrożenie wymaga hosta Linuksa z:

```text
Docker Engine
Git
Nginx
OpenSSL
Network connectivity
Persistent storage
```

Serwer musi mieć wystarczająco dużo miejsca na:

```text
Docker images
SQLite database
Application data
Logs
Backups
```

Sama aplikacja LUMS działa wewnątrz Docker.

---

## 6.2 Klienci Linuksa

Zarządzani klienci Linuksa wymagają:

```text
Python 3
systemd
Supported package manager
Network connectivity to the LUMS server
Valid client token
Trusted TLS certificate
```

Obsługiwane rodziny menedżerów pakietów:

```text
Debian / Ubuntu
    APT / dpkg

Arch Linux
    pacman
```

Klient musi być w stanie osiągnąć punkt końcowy HTTPS LUMS.

---

# 7. Zalecany układ katalogów

Zalecana lokalizacja repozytorium po stronie serwera:

```text
/opt/lums-public/
```

Repozytorium zawiera źródło aplikacji, źródło agenta i testy.

Typowa instalacja używa:

```text
/opt/lums-public/
    ├── agent/
    ├── server/
    ├── tests/
    ├── Dockerfile
    ├── requirements.txt
    └── requirements-dev.txt
```

Konfiguracja po stronie hosta jest przechowywana poza repozytorium:

```text
/etc/lums/
    ├── secrets/
    │   └── lums_secret
    └── tls/
        ├── lums.crt
        └── lums.key
```

Trwałe dane aplikacji są przechowywane w:

```text
lums-data:/var/lib/lums
```

Baza danych SQLite to:

```text
/var/lib/lums/lums.db
```

Baza danych nigdy nie może być przechowywana wewnątrz drzewa roboczego Git.

Sekrety i prywatny materiał TLS również muszą pozostać poza repozytorium.

---

# 8. Przygotowanie repozytorium

Sklonuj repozytorium do zamierzonego katalogu instalacji:

```bash
sudo mkdir -p /opt
cd /opt

sudo git clone \
    https://github.com/NovaForgeCtrl/LUMS.git \
    lums-public
```

Wejdź do repozytorium:

```bash
cd /opt/lums-public
```

Sprawdź drzewo robocze:

```bash
git status
```

Sprawdź bieżącą rewizję:

```bash
git log -1 --oneline --decorate
```

W przypadku kontrolowanych wdrożeń należy zapisać dokładny commit użyty do instalacji.

Nie buduj obrazów produkcyjnych z nieznanego lub niezweryfikowanego drzewa roboczego.

---

# 9. Kontrola bezpieczeństwa repozytorium

Przed zbudowaniem obrazu produkcyjnego sprawdź, czy poufne pliki nie zostały umieszczone w repozytorium.

Przejrzyj drzewo robocze:

```bash
git status --short
```

Przejrzyj ignorowane pliki tam, gdzie to stosowne:

```bash
git status --ignored --short
```

Repozytorium nie może zawierać:

```text
Production database files
Private TLS keys
Application secrets
Client tokens
Credential dumps
Backup databases
Runtime logs
Temporary backup files
```

Projekt używa reguł ignorowania repozytorium, aby zapobiec przypadkowemu śledzeniu typowych artefaktów kopii zapasowych.

Przed zatwierdzeniem zmian dokładnie sprawdź listę przygotowanych plików.

---

# 10. Przygotowanie katalogów konfiguracji hosta

Utwórz wymagane katalogi po stronie hosta:

```bash
sudo install -d -m 700 /etc/lums
sudo install -d -m 700 /etc/lums/secrets
sudo install -d -m 700 /etc/lums/tls
```

Katalog sekretów zawiera sekret aplikacji.

Katalog TLS zawiera certyfikat TLS i klucz prywatny.

Ochrona tych katalogów zmniejsza ryzyko przypadkowego ujawnienia.

Sprawdź:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums \
    /etc/lums/secrets \
    /etc/lums/tls
```

---

# 11. Utworzenie sekretu aplikacji

Sekret aplikacji LUMS jest przechowywany na hoście, a nie osadzany bezpośrednio w obrazie Docker.

Ścieżka sekretu produkcyjnego to:

```text
/etc/lums/secrets/lums_secret
```

Wygeneruj losowy sekret:

```bash
sudo sh -c 'umask 077 && openssl rand -hex 32 > /etc/lums/secrets/lums_secret'
```

Ochronij wynikowy plik:

```bash
sudo chmod 600 \
    /etc/lums/secrets/lums_secret
```

Sprawdź uprawnienia bez wyświetlania sekretu:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/secrets/lums_secret
```

Oczekiwane:

```text
600
```

Sekret nigdy nie może być:

```text
Committed to Git
Printed into logs
Included in the Docker image
Placed into screenshots
Published in issues
Included in documentation
```

Kontener otrzymuje sekret poprzez bind mount tylko do odczytu.

---

# 12. Przygotowanie materiału TLS

LUMS używa HTTPS do dostępu zewnętrznego.

Zalecane lokalizacje po stronie hosta to:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Zainstaluj odpowiedni certyfikat i klucz prywatny przed konfiguracją Nginx.

Chroń klucz prywatny:

```bash
sudo chmod 600 \
    /etc/lums/tls/lums.key
```

Certyfikat może być czytelny dla usługi Nginx:

```bash
sudo chmod 644 \
    /etc/lums/tls/lums.crt
```

Sprawdź:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

Klucz prywatny nigdy nie może być zatwierdzony w Git ani zawarty w obrazie Docker.

---

# 13. Zasada instalacji

Instalacja powinna przebiegać w kontrolowanych etapach:

```text
Repository
    ↓
Host configuration
    ↓
Application secret
    ↓
TLS material
    ↓
Docker image
    ↓
Persistent volume
    ↓
Hardened container
    ↓
Nginx / HTTPS
    ↓
Administrator
    ↓
Server validation
    ↓
Linux clients
```

Nie podłączaj klientów produkcyjnych, zanim serwer nie przejdzie własnych kontroli walidacyjnych.

Kolejne sekcje kontynuują z budową obrazu Docker i utwardzonym wdrożeniem produkcyjnym.

# 14. Zbudowanie obrazu Docker LUMS

Przed zbudowaniem obrazu produkcyjnego upewnij się, że repozytorium jest w zamierzonym stanie.

Wejdź do repozytorium:

```bash
cd /opt/lums-public
```

Uruchom zestaw testów przed utworzeniem obrazu produkcyjnego:

```bash
./.venv-test/bin/pytest -q
```

Oczekuje się, że liczba testów będzie rosnąć w miarę rozwoju projektu.

Ważnym wymogiem jest pomyślne zakończenie odpowiedniego zestawu testów przed wdrożeniem.

Zbuduj obraz Docker:

```bash
sudo docker build \
    -t lums:latest \
    .
```

Sprawdź, czy obraz istnieje:

```bash
sudo docker image ls lums
```

Sprawdź obraz:

```bash
sudo docker image inspect lums:latest
```

Obraz produkcyjny jest oparty na przypiętym obrazie bazowym Python 3.13 slim.

Dockerfile używa również przypiętych zależności produkcyjnych tam, gdzie to wymagane.

---

# 15. Przegląd budowania Docker

Przed wdrożeniem obrazu przejrzyj wynik budowania pod kątem nieoczekiwanych błędów lub ostrzeżeń.

Sprawdź wynikowy obraz:

```bash
sudo docker inspect \
    lums:latest
```

Sprawdź skonfigurowanego użytkownika aplikacji:

```bash
sudo docker image inspect \
    lums:latest \
    --format '{{.Config.User}}'
```

Aplikacja ma działać jako:

```text
lums
```

Aplikacja nie może wymagać uprawnień root podczas normalnego wykonania.

Przejrzyj Dockerfile przy zmianie procesu budowania:

```bash
sed -n '1,240p' Dockerfile
```

Nie dodawaj sekretów, certyfikatów ani baz danych produkcyjnych do kontekstu budowania Docker.

Repozytorium zawiera plik `.dockerignore`, aby zmniejszyć ryzyko przypadkowego włączenia artefaktów wykonawczych do obrazu.

---

# 16. Utworzenie trwałego wolumenu Docker

Utwórz trwały wolumen danych LUMS:

```bash
sudo docker volume create lums-data
```

Sprawdź:

```bash
sudo docker volume inspect lums-data
```

Wolumen przechowuje trwałe dane aplikacji:

```text
lums-data
    ↓
/var/lib/lums
    ↓
/var/lib/lums/lums.db
```

Sam system plików kontenera nie może być traktowany jako trwałe przechowywanie aplikacji.

Dlatego baza danych przetrwa zastąpienie kontenera, dopóki wolumen `lums-data` jest zachowany.

> [!IMPORTANT]
> Nigdy nie usuwaj `lums-data` podczas normalnej aktualizacji aplikacji.

Usunięcie wolumenu usuwa bazę danych SQLite przechowywaną w nim.

---

# 17. Sprawdzenie trwałego wolumenu

Przed uruchomieniem LUMS potwierdź, że wolumen istnieje:

```bash
sudo docker volume inspect \
    lums-data
```

Wolumen można sprawdzić również przez Docker:

```bash
sudo docker volume ls | grep lums-data
```

Nowo utworzony wolumen zwykle nie zawiera jeszcze bazy danych.

Baza danych jest inicjalizowana przez aplikację LUMS podczas wdrożenia.

---

# 18. Konfiguracja kontenera produkcyjnego

Kontener produkcyjny używa jednocześnie kilku kontroli bezpieczeństwa.

Oczekiwana podstawa środowiska wykonawczego:

```text
Non-root user
Read-only root filesystem
All Linux capabilities dropped
no-new-privileges
No privileged mode
Localhost-only application binding
Read-only application-secret mount
Persistent writable data volume
Dedicated /tmp tmpfs
```

Port aplikacji jest publikowany tylko na localhost:

```text
127.0.0.1:5050 → container:5000
```

Zewnętrzny punkt końcowy HTTPS jest zapewniony przez Nginx.

---

# 19. Uruchomienie utwardzonego kontenera LUMS

Przed uruchomieniem nowego kontenera produkcyjnego upewnij się, że inny kontener o nazwie `lums` nie jest już uruchomiony:

```bash
sudo docker ps \
    --filter name=lums
```

Jeśli zastępowane jest istniejące wdrożenie, zachowaj istniejący kontener, dopóki nowy obraz nie zostanie zwalidowany.

Uruchom utwardzony kontener:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --security-opt=no-new-privileges:true \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --tmpfs /run:rw,noexec,nosuid,size=16m \
    -p 127.0.0.1:5050:5000 \
    -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
    -v lums-data:/var/lib/lums \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    lums:latest
```

Sekret aplikacji jest zamontowany tylko do odczytu.

Baza danych SQLite jest przechowywana w trwałym wolumenie.

System plików główny jest tylko do odczytu.

Wszystkie uprawnienia Linuksa są usuwane.

Opcja bezpieczeństwa `no-new-privileges` zapobiega uzyskaniu przez procesy wewnątrz kontenera dodatkowych uprawnień.

---

# 20. Sprawdzenie stanu kontenera

Sprawdź działający kontener:

```bash
sudo docker ps \
    --filter name=lums
```

Oczekiwany stan:

```text
Up ...
```

Sprawdź stan kontenera bezpośrednio:

```bash
sudo docker inspect \
    --format '{{.State.Status}}' \
    lums
```

Oczekiwane:

```text
running
```

Sprawdź ostatnie logi:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Błędy uruchamiania aplikacji muszą zostać rozwiązane przed kontynuowaniem instalacji.

---

# 21. Sprawdzenie bezpieczeństwa kontenera

Sprawdź efektywną konfigurację bezpieczeństwa środowiska wykonawczego:

```bash
sudo docker inspect lums \
    --format='User={{.Config.User}} ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} Privileged={{.HostConfig.Privileged}} CapDrop={{json .HostConfig.CapDrop}} SecurityOpt={{json .HostConfig.SecurityOpt}}'
```

Oczekiwana podstawa:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

Dokładne formatowanie wyjścia Docker może się różnić.

Liczy się efektywna konfiguracja.

---

# 22. Sprawdzenie portu aplikacji

Sprawdź opublikowany port Docker:

```bash
sudo docker port lums
```

Oczekiwane:

```text
5000/tcp -> 127.0.0.1:5050
```

Następujące **nie** jest akceptowalne dla aplikacji produkcyjnej:

```text
0.0.0.0:5050
```

lub:

```text
0.0.0.0:5000
```

Aplikacja jest celowo dostępna tylko poprzez lokalną ścieżkę reverse proxy.

Sprawdź gniazda nasłuchujące:

```bash
sudo ss -lntp | grep -E ':5050|:5000'
```

Powinno być obecne tylko powiązanie aplikacji z localhost.

---

# 23. Sprawdzenie montażu sekretu

Potwierdź, że sekret jest zamontowany:

```bash
sudo docker inspect lums \
    --format='{{range .Mounts}}{{println .Source "->" .Destination "RW=" .RW}}{{end}}'
```

Sekret aplikacji powinien wyglądać podobnie do:

```text
/etc/lums/secrets/lums_secret -> /run/secrets/lums_secret RW=false
```

Dokładne wyjście może zawierać dodatkowe informacje o montażu.

Ważną właściwością jest:

```text
RW=false
```

Nigdy nie wyświetlaj zawartości sekretu.

Wystarczy bezpośredni test czytelności:

```bash
sudo docker exec lums \
    sh -c 'test -r /run/secrets/lums_secret && echo "secret mount: OK"'
```

Oczekiwane:

```text
secret mount: OK
```

---

# 24. Sprawdzenie montażu trwałego wolumenu

Sprawdź montaże kontenera:

```bash
sudo docker inspect lums \
    --format='{{range .Mounts}}{{println .Type .Source "->" .Destination "RW=" .RW}}{{end}}'
```

Wolumen danych LUMS musi być zamontowany w:

```text
/var/lib/lums
```

i musi być zapisywalny:

```text
RW=true
```

Oczekiwana relacja to:

```text
lums-data
    ↓
/var/lib/lums
```

System plików główny pozostaje tylko do odczytu, podczas gdy dedykowany wolumen danych zapewnia wymagany trwały dostęp do zapisu.

---

# 25. Sprawdzenie systemu plików głównego tylko do odczytu

System plików główny aplikacji musi być tylko do odczytu.

Środowisko wykonawcze kontenera powinno raportować:

```text
ReadonlyRootfs=true
```

Wewnątrz kontenera można wykonać kontrolowany test zapisu.

Na przykład:

```bash
sudo docker exec lums \
    sh -c 'touch /app/.write-test'
```

Polecenie powinno się nie powieść, ponieważ `/app` jest częścią systemu plików kontenera tylko do odczytu.

Nie wyłączaj systemu plików głównego tylko do odczytu tylko dlatego, że komponent aplikacji próbuje pisać poza wyznaczonymi zapisywalnymi lokalizacjami.

Jeśli aplikacja wymaga trwałych danych, użyj odpowiedniego wolumenu lub systemu plików środowiska wykonawczego.

---

# 26. Sprawdzenie zapisywalnego systemu plików tymczasowych

Kontener zapewnia dedykowany tmpfs `/tmp`.

Sprawdź:

```bash
sudo docker exec lums \
    sh -c 'touch /tmp/lums-write-test && rm -f /tmp/lums-write-test && echo "tmpfs: OK"'
```

Oczekiwane:

```text
tmpfs: OK
```

System plików tymczasowych jest skonfigurowany z:

```text
noexec
nosuid
```

oraz limitem rozmiaru.

Zapewnia to tymczasowe zapisywalne przechowywanie bez czynienia systemu plików głównego kontenera zapisywalnym.

---

# 27. Sprawdzenie katalogu danych aplikacji

Aplikacja LUMS wymaga dostępu do zapisu w swoim trwałym katalogu danych.

Test:

```bash
sudo docker exec lums \
    sh -c 'touch /var/lib/lums/.write-test && rm -f /var/lib/lums/.write-test && echo "data volume: OK"'
```

Oczekiwane:

```text
data volume: OK
```

To potwierdza, że dedykowany zapisywalny wolumen jest dostępny, podczas gdy reszta kontenera pozostaje tylko do odczytu.

---

# 28. Sprawdzenie użytkownika aplikacji

Potwierdź efektywnego użytkownika środowiska wykonawczego:

```bash
sudo docker exec lums \
    id
```

Proces powinien działać jako nieuprzywilejowany użytkownik LUMS.

Oczekiwana tożsamość obejmuje:

```text
uid=10001(lums)
```

Dokładne informacje o grupie mogą się różnić w zależności od konfiguracji obrazu.

Kontener nie może działać jako:

```text
root
```

podczas normalnego działania.

---

# 29. Inicjalizacja bazy danych

Po uruchomieniu kontenera sprawdź, czy baza danych istnieje:

```bash
sudo docker exec lums \
    ls -lh /var/lib/lums/lums.db
```

Jeśli aplikacja została pomyślnie zainicjalizowana, baza danych powinna być obecna.

Baza danych znajduje się w:

```text
/var/lib/lums/lums.db
```

wewnątrz kontenera i fizycznie przetrwa poprzez:

```text
lums-data
```

Baza danych nie może być kopiowana do:

```text
/opt/lums-public
```

ani zatwierdzana w Git.

---

# 30. Sprawdzenie konfiguracji środowiska wykonawczego SQLite

Obecna produkcyjna podstawa LUMS używa:

```text
journal_mode = wal
busy_timeout = 5000 ms
synchronous = 2
foreign_keys = ON
```

Aplikacja jawnie włącza wymuszanie kluczy obcych dla połączeń z bazą danych.

Baza danych używa trybu WAL do normalnego działania produkcyjnego.

Konfigurację środowiska wykonawczego można sprawdzić z bazy danych aplikacji.

Na przykład:

```bash
sudo docker exec -i lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

for pragma in (
    "journal_mode",
    "busy_timeout",
    "synchronous",
    "foreign_keys",
):
    print(f"{pragma}={db.execute(f'PRAGMA {pragma}').fetchone()[0]}")

db.close()
PY
```

Oczekiwane wartości są równoważne:

```text
journal_mode=wal
busy_timeout=5000
synchronous=2
foreign_keys=0
```

Aplikacja jawnie włącza klucze obce.

---

# 31. Sprawdzenie integralności bazy danych

Uruchom kontrolę integralności SQLite:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
result = db.execute("PRAGMA integrity_check").fetchone()[0]
print(result)
db.close()
PY
```

Oczekiwane:

```text
ok
```

Nie kontynuuj wdrożenia, jeśli kontrola integralności zgłasza uszkodzenie bazy danych.

---

# 32. Sprawdzenie migracji bazy danych

LUMS używa migracji aplikacji do zmian schematu bazy danych.

Sprawdź pliki związane z migracjami:

```bash
ls -lh \
    server/*migration*.py
```

Aplikacja wykonuje wymagane migracje podczas uruchamiania/wdrożenia zgodnie z obecną implementacją.

Po uruchomieniu sprawdź logi aplikacji:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Błędy migracji muszą zostać zbadane przed utworzeniem użytkowników lub podłączeniem klientów.

Nie modyfikuj ręcznie schematu SQLite produkcyjnego, chyba że dokumentacja projektu wyraźnie tego wymaga.

---

# 33. Lokalna walidacja aplikacji

Przed konfiguracją Nginx potwierdź, że aplikacja odpowiada lokalnie.

Aplikacja Docker jest powiązana z:

```text
127.0.0.1:5050
```

Lokalne żądanie można przetestować za pomocą:

```bash
curl -I \
    http://127.0.0.1:5050/
```

Dokładna odpowiedź HTTP zależy od bieżącej trasy aplikacji i stanu uwierzytelniania.

Ważnym wymogiem jest to, że żądanie dociera do działającej aplikacji LUMS.

Jeśli połączenie się nie powiedzie, sprawdź:

```bash
sudo docker ps \
    --filter name=lums
```

oraz:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Nie udostępniaj portu `5050` na zewnątrz jako obejścia do rozwiązywania problemów.

---

# 34. Wstępny punkt kontrolny serwera

Na tym etapie serwer powinien spełniać:

```text
[ ] Repository cloned
[ ] Working tree reviewed
[ ] Production tests completed
[ ] Docker image built
[ ] Persistent lums-data volume exists
[ ] Hardened container running
[ ] Container runs as lums
[ ] Root filesystem is read-only
[ ] All capabilities are dropped
[ ] no-new-privileges is enabled
[ ] Privileged mode is disabled
[ ] Secret is mounted read-only
[ ] Persistent data volume is mounted
[ ] Port 5050 is localhost-only
[ ] SQLite database exists
[ ] SQLite integrity check succeeds
[ ] Foreign keys are enabled
[ ] Local application endpoint responds
```

Nie podłączaj jeszcze klientów produkcyjnych.

Następny etap konfiguruje Nginx, HTTPS i zewnętrzny punkt końcowy LUMS.

# 35. Konfiguracja Nginx

Nginx zapewnia zewnętrzny punkt wejścia HTTPS dla LUMS.

Sama aplikacja pozostaje powiązana z:

```text
127.0.0.1:5050
```

Zamierzona ścieżka żądania to:

```text
Client
   │
   │ HTTPS
   ▼
Nginx :443
   │
   │ HTTP localhost
   ▼
127.0.0.1:5050
   │
   ▼
LUMS container :5000
```

Utwórz konfigurację witryny Nginx:

```bash
sudo tee /etc/nginx/sites-available/lums > /dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;

    server_name LUMS-SERVER;

    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;

    server_name LUMS-SERVER;

    ssl_certificate     /etc/lums/tls/lums.crt;
    ssl_certificate_key /etc/lums/tls/lums.key;

    location / {
        proxy_pass http://127.0.0.1:5050;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

Zastąp:

```text
LUMS-SERVER
```

nazwą hosta lub adresem używanym przez instalację.

Nie używaj literalnego symbolu zastępczego w konfiguracji produkcyjnej.

---

# 36. Włączenie konfiguracji Nginx LUMS

Utwórz dowiązanie włączonej witryny:

```bash
sudo ln -s \
    /etc/nginx/sites-available/lums \
    /etc/nginx/sites-enabled/lums
```

Jeśli domyślna witryna Nginx nie jest wymagana, usuń ją:

```bash
sudo rm -f \
    /etc/nginx/sites-enabled/default
```

Nie usuwaj innych konfiguracji Nginx należących do niepowiązanych aplikacji.

---

# 37. Walidacja konfiguracji Nginx

Zawsze testuj konfigurację przed przeładowaniem Nginx:

```bash
sudo nginx -t
```

Oczekiwane:

```text
syntax is ok
test is successful
```

Dopiero po pomyślnym teście konfiguracji należy przeładować Nginx:

```bash
sudo systemctl reload nginx
```

Sprawdź usługę:

```bash
sudo systemctl status \
    nginx \
    --no-pager
```

Nginx musi działać przed kontynuowaniem walidacji HTTPS.

---

# 38. Sprawdzenie plików certyfikatu TLS

Potwierdź, że skonfigurowane pliki certyfikatów istnieją:

```bash
sudo ls -lh \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

Sprawdź uprawnienia:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/lums/tls/lums.crt \
    /etc/lums/tls/lums.key
```

Klucz prywatny powinien normalnie mieć:

```text
600
```

Certyfikat może normalnie mieć:

```text
644
```

Nigdy nie wyświetlaj zawartości klucza prywatnego.

---

# 39. Sprawdzenie punktu końcowego HTTPS

Przetestuj HTTPS lokalnie:

```bash
curl -I \
    https://LUMS-SERVER/
```

Zastąp `LUMS-SERVER` nazwą hosta objętą certyfikatem TLS serwera. Nie używaj `-k` do rutynowej weryfikacji; pomija to walidację certyfikatu.

Gdy certyfikat jest zaufany przez system, użyj weryfikacji certyfikatu:

```bash
curl -I \
    https://LUMS-SERVER/
```

Pomyślna odpowiedź potwierdza, że żądanie dociera do punktu końcowego HTTPS Nginx.

Dokładny status HTTP zależy od żądanej trasy i stanu uwierzytelniania.

Ważnym wymogiem jest to, że połączenie TLS się powiedzie, a żądanie dotrze do LUMS.

---

# 40. Sprawdzenie przekierowania HTTP na HTTPS

Listener HTTP musi przekierowywać klientów na HTTPS.

Test:

```bash
curl -I \
    http://LUMS-SERVER/
```

Oczekiwane zachowanie:

```text
HTTP/1.1 301 ...
Location: https://...
```

Aplikacja LUMS nie powinna być obsługiwana przez niezaszyfrowane połączenie HTTP.

Nie konfiguruj trwale klientów z wyłączoną weryfikacją certyfikatów tylko dlatego, że początkowy certyfikat nie jest zaufany.

Zamiast tego napraw konfigurację zaufania.

---

# 41. Sprawdzenie zewnętrznej ścieżki sieciowej

Sprawdź gniazda nasłuchujące:

```bash
sudo ss -lntp | grep -E ':80|:443|:5050|:5000'
```

Zamierzona architektura to:

```text
80
 │
 └── HTTP redirect
        │
        ▼
443
 │
 └── Nginx
        │
        ▼
127.0.0.1:5050
        │
        ▼
Docker :5000
```

Port `5050` nie może być udostępniany w sieci LAN.

Port `5000` nie może być udostępniany bezpośrednio.

Port aplikacji Docker jest wewnętrznym punktem końcowym reverse proxy.

---

# 42. Sprawdzenie nagłówków bezpieczeństwa

Sprawdź nagłówki odpowiedzi HTTPS:

```bash
curl -I \
    https://LUMS-SERVER/
```

Przejrzyj zwrócone nagłówki, zamiast zakładać, że konfiguracja bezpieczeństwa jest aktywna.

Istotne nagłówki bezpieczeństwa mogą obejmować:

```text
X-Content-Type-Options
X-Frame-Options
Referrer-Policy
Content-Security-Policy
```

Dokładne nagłówki zależą od bieżącej aplikacji LUMS i konfiguracji Nginx.

Jeśli brakuje wymaganego nagłówka, sprawdź efektywną konfigurację Nginx:

```bash
sudo nginx -T
```

oraz konfigurację aplikacji:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Nie dodawaj nagłówków bezpieczeństwa na ślepo, nie sprawdzając, która warstwa już za nie odpowiada.

---

# 43. Sprawdzenie obsługi hosta

Wdrożenie produkcyjne nie powinno ujawniać aplikacji przez niezamierzoną domyślną witrynę Nginx.

Przejrzyj aktywną konfigurację:

```bash
sudo nginx -T
```

Sprawdź włączone witryny:

```bash
ls -la \
    /etc/nginx/sites-enabled/
```

Zamierzony wirtualny host LUMS powinien być obecny.

Domyślna witryna nie powinna nieoczekiwanie obsługiwać aplikacji LUMS.

Gdy jako punkt końcowy LUMS używany jest adres IP, upewnij się, że skonfigurowany `server_name` i certyfikat pasują do rzeczywistego modelu wdrożenia.

---

# 44. Ponowne sprawdzenie ekspozycji Docker

Po skonfigurowaniu Nginx potwierdź, że aplikacja pozostaje ograniczona do localhost:

```bash
sudo docker port lums
```

Oczekiwane:

```text
5000/tcp -> 127.0.0.1:5050
```

Reverse proxy nie wymaga zmiany powiązania Docker.

Nie zmieniaj go na:

```text
0.0.0.0:5050
```

tylko dlatego, że Nginx nasłuchuje w sieci.

Nginx i Docker mają celowo oddzielne granice ekspozycji.

---

# 45. Utworzenie początkowego administratora

Początkowy administrator musi zostać utworzony przy użyciu mechanizmu inicjalizacji administratora bieżącego repozytorium.

Przed uruchomieniem polecenia inicjalizacyjnego sprawdź dostępną implementację repozytorium:

```bash
cd /opt/lums-public
```

Przejrzyj pliki inicjalizacyjne związane z bezpieczeństwem:

```bash
find server \
    -maxdepth 1 \
    -type f \
    -iname '*security*' \
    -o -iname '*migration*'
```

Następnie sprawdź bieżącą implementację migracji/inicjalizacji przed jej wykonaniem.

Na przykład:

```bash
sed -n '1,260p' \
    server/security_migration.py
```

Użyj procedury inicjalizacji dostarczonej przez dokładną rewizję repozytorium, która jest wdrażana.

> [!IMPORTANT]
> Nie kopiuj hasła administratora do historii powłoki ani dokumentacji.

Początkowy administrator musi otrzymać:

```text
role = administrator
```

Konto administratora jest wymagane do pierwszego logowania webowego i późniejszej administracji klientami.

---

# 46. Sprawdzenie konta administratora

Po inicjalizacji administratora sprawdź konto bez ujawniania materiału uwierzytelniania.

Inspekcję bazy danych można wykonać z kontenera:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

rows = db.execute(
    """
    SELECT id, username, enabled, role
    FROM users
    ORDER BY id
    """
).fetchall()

for row in rows:
    print(row)

db.close()
PY
```

Oczekiwane właściwości administratora obejmują:

```text
enabled = 1
role = administrator
```

Nie wyświetlaj:

```text
password hashes
session data
client tokens
application secrets
```

---

# 47. Hasło administratora

Użyj unikalnego hasła administratora.

Hasło nie powinno być ponownie używane z:

```text
other servers
Linux accounts
GitHub accounts
email accounts
network devices
other LUMS installations
```

Aplikacja LUMS przechowuje hasła przy użyciu skonfigurowanego mechanizmu hashowania haseł.

Nie próbuj ręcznie zastępować hasha hasła aplikacji w SQLite.

Jeśli hasło administratora musi zostać zmienione, użyj obsługiwanego mechanizmu aplikacji.

---

# 48. Pierwsze logowanie webowe

Otwórz punkt końcowy HTTPS LUMS:

```text
https://LUMS-SERVER/
```

Zaloguj się na konto administratora.

Po uwierzytelnieniu administrator powinien mieć dostęp do interfejsu administracyjnego.

Interfejs administratora powinien zapewniać dostęp do obszarów dozwolonych przez obecną implementację RBAC.

Co najmniej administrator powinien mieć dostęp do:

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
User management
```

---

# 49. Sprawdzenie RBAC administratora

Po zalogowaniu sprawdź, czy funkcje administracyjne są dostępne.

Administrator powinien mieć dostęp do zarządzania użytkownikami.

Administrator powinien również móc wykonywać operacje zarządzania klientami dozwolone przez obecną implementację.

Autoryzacja po stronie serwera pozostaje granicą bezpieczeństwa.

Interfejs przeglądarki nie jest zaufany tylko dlatego, że element jest widoczny lub ukryty.

---

# 50. Utworzenie operatora

Po zweryfikowaniu konta administratora utwórz konto operatora poprzez interfejs zarządzania użytkownikami LUMS.

Rola operatora jest przeznaczona do operacyjnego zarządzania aktualizacjami.

Operator może uzyskać dostęp do:

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
```

Operator nie może wykonywać funkcji wyłącznie administracyjnych, takich jak:

```text
User management
Role management
Client creation/disabling
Client-token rotation
```

Sprawdź uprawnienia przy użyciu interfejsu aplikacji i, gdzie to stosowne, zachowania autoryzacji API.

---

# 51. Utworzenie Viewera

Konto Viewera można utworzyć, gdy wymagany jest dostęp tylko do odczytu.

Rola Viewera jest celowo ograniczona.

Viewer może uzyskać dostęp do:

```text
Clients
Installed software
```

Następujące obszary nie mogą być dostępne dla Viewera:

```text
Available updates
Update jobs
Update history
Package management
System maintenance
```

Te ograniczenia są egzekwowane po stronie serwera.

Interfejs może dodatkowo ukrywać niedostępne funkcje.

---

# 52. Sprawdzenie izolacji Viewera

Zaloguj się na konto Viewera i sprawdź widoczny interfejs.

Viewer nie powinien otrzymywać kontrolek zarządzania.

Viewer nie może obejść UI i wywołać chronionych punktów końcowych bezpośrednio.

Dla chronionych operacji powinien zostać zwrócony błąd autoryzacji.

Oczekiwana zasada to:

```text
UI restriction
     +
server-side authorization
     =
RBAC boundary
```

Nigdy nie polegaj na JavaScript lub ukrytych elementach HTML jako jedynym mechanizmie autoryzacji.

---

# 53. Sprawdzenie ochrony sesji i CSRF

Po pierwszym pomyślnym logowaniu sprawdź, czy aplikacja używa skonfigurowanych mechanizmów ochrony sesji i CSRF.

Instalacja nie powinna wyłączać ochrony CSRF, aby żądania API lub akcje przeglądarki działały.

Jeśli legalne żądanie kończy się błędem CSRF, sprawdź przepływ aplikacji, zamiast wyłączać ochronę.

Zachowanie związane z sesjami jest udokumentowane w:

```text
docs/security.md
```

---

# 54. Sprawdzenie ograniczania szybkości logowania

Obecna ochrona logowania używa trwałego śledzenia niepowodzeń.

Skonfigurowana progresja to:

```text
5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

Pomyślne uwierzytelnienie czyści odpowiedni stan niepowodzenia.

Nie wywołuj wielokrotnie nieudanego uwierzytelniania wobec instalacji produkcyjnej tylko po to, aby przetestować mechanizm.

Użyj istniejącego zestawu testów do powtarzalnej automatycznej walidacji.

---

# 55. Punkt kontrolny walidacji serwera

Na tym etapie sprawdź:

```text
[ ] Nginx is running
[ ] Nginx configuration passes nginx -t
[ ] TLS certificate is installed
[ ] TLS private key is protected
[ ] HTTPS works
[ ] HTTP redirects to HTTPS
[ ] Docker remains localhost-only
[ ] Port 5000 is not externally exposed
[ ] Security headers are present as configured
[ ] Default Nginx site is not unintentionally serving LUMS
[ ] Administrator account exists
[ ] Administrator can log in
[ ] Administrator RBAC works
[ ] Operator role can be created
[ ] Viewer role can be created
[ ] Viewer restrictions are enforced server-side
[ ] CSRF protection remains enabled
[ ] Session protection remains enabled
```

Dopiero po przejściu przez serwer tych kontroli należy instalować klientów Linuksa.

Następna sekcja obejmuje agenta Linuksa, konfigurację klienta, zaufanie TLS i integrację z systemd.

# 56. Instalacja klienta Linuksa

Klienci LUMS to systemy Linuksa zarządzane przez serwer LUMS.

Instalacja klienta składa się z:

```text
Linux system
    ↓
LUMS Agent
    ↓
Client configuration
    ↓
Client token
    ↓
TLS trust
    ↓
systemd service
    ↓
Reporting timer
```

Wykonanie aktualizacji jest obsługiwane oddzielnie przez watcher wykonania.

Obecna wersja agenta:

```text
1.7.0
```

Obecna wersja watchera:

```text
1.2.1
```

---

# 57. Obsługiwani klienci Linuksa

Obecne implementacje zarządzania pakietami obsługują:

```text
Debian / Ubuntu
    ↓
APT / dpkg

Arch Linux
    ↓
pacman
```

Sprawdź system operacyjny przed zainstalowaniem klienta:

```bash
cat /etc/os-release
```

Sprawdź architekturę:

```bash
uname -m
```

Sprawdź systemd:

```bash
systemctl --version
```

Klient wymaga działającej instalacji systemd.

---

# 58. Wymagania sieciowe klienta

Klient musi być w stanie osiągnąć punkt końcowy HTTPS LUMS.

Przetestuj podstawową łączność sieciową:

```bash
ping LUMS-SERVER
```

Pomyślny ping nie jest wymagany, gdy ICMP jest blokowany.

Ważnym wymogiem jest łączność HTTPS.

Przetestuj punkt końcowy LUMS:

```bash
curl -I \
    https://LUMS-SERVER/
```

Jeśli serwer używa prywatnego CA, klient musi zaufać temu CA przed kontynuowaniem.

Nie wyłączaj weryfikacji TLS jako trwałego obejścia.

---

# 59. Uzyskanie agenta LUMS

Źródło agenta jest zawarte w repozytorium LUMS.

Na kliencie uzyskaj repozytorium lub w inny sposób przenieś wymagane pliki agenta przez zatwierdzoną metodę wdrożenia.

Odpowiednie pliki to:

```text
agent/agent.py
agent/watcher.py
agent/package_manager.py
```

Zalecany katalog instalacji to:

```text
/opt/lums-agent
```

Utwórz go:

```bash
sudo install -d -m 755 \
    /opt/lums-agent
```

---

# 60. Instalacja plików agenta

Z repozytorium LUMS:

```bash
cd /opt/lums-public
```

Zainstaluj agenta:

```bash
sudo cp \
    agent/agent.py \
    /opt/lums-agent/agent.py
```

Zainstaluj watcher:

```bash
sudo cp \
    agent/watcher.py \
    /opt/lums-agent/watcher.py
```

Zainstaluj abstrakcję menedżera pakietów:

```bash
sudo cp \
    agent/package_manager.py \
    /opt/lums-agent/package_manager.py
```

Sprawdź:

```bash
ls -lh \
    /opt/lums-agent/
```

Katalog powinien zawierać zainstalowane komponenty agenta.

---

# 61. Sprawdzenie wersji agenta

Sprawdź zainstalowaną wersję agenta:

```bash
grep -n \
    'AGENT_VERSION' \
    /opt/lums-agent/agent.py
```

Obecna wersja to:

```text
1.7.0
```

Sprawdź watcher:

```bash
grep -n \
    'WATCHER_VERSION' \
    /opt/lums-agent/watcher.py
```

Obecna wersja to:

```text
1.2.1
```

Jeśli zainstalowane wersje nie pasują do zamierzonej rewizji wdrożenia, zatrzymaj się i sprawdź, czy używana jest właściwa rewizja repozytorium.

---

# 62. Instalacja plików usług systemd

Agent i watcher używają oddzielnych usług systemd.

Zainstaluj usługę agenta:

```bash
sudo cp \
    agent/lums-agent.service \
    /etc/systemd/system/lums-agent.service
```

Zainstaluj usługę watchera:

```bash
sudo cp \
    agent/lums-agent-watcher.service \
    /etc/systemd/system/lums-agent-watcher.service
```

Zainstaluj timer raportowania:

```bash
sudo cp \
    agent/lums-agent.timer \
    /etc/systemd/system/lums-agent.timer
```

Zainstaluj timer watchera:

```bash
sudo cp \
    agent/lums-agent-watcher.timer \
    /etc/systemd/system/lums-agent-watcher.timer
```

Przeładuj systemd:

```bash
sudo systemctl daemon-reload
```

---

# 63. Sprawdzenie jednostek systemd

Sprawdź usługę agenta:

```bash
systemctl cat \
    lums-agent.service
```

Sprawdź usługę watchera:

```bash
systemctl cat \
    lums-agent-watcher.service
```

Sprawdź timer agenta:

```bash
systemctl cat \
    lums-agent.timer
```

Sprawdź timer watchera:

```bash
systemctl cat \
    lums-agent-watcher.timer
```

Jednostki powinny odwoływać się do zainstalowanych plików w:

```text
/opt/lums-agent/
```

Nie włączaj timerów, dopóki konfiguracja klienta i uwierzytelnianie nie zostaną ukończone.

---

# 64. Utworzenie konfiguracji klienta

Konfiguracja klienta jest przechowywana poza repozytorium Git.

Użyj:

```text
/etc/default/lums-agent
```

Utwórz plik:

```bash
sudo install -m 600 /dev/null \
    /etc/default/lums-agent
```

Konfiguracja zawiera punkt końcowy serwera LUMS i token klienta.

Przykładowa struktura:

```text
LUMS_BASE=https://LUMS-SERVER
LUMS_TOKEN=<CLIENT-TOKEN>
```

Zastąp:

```text
LUMS-SERVER
```

rzeczywistym punktem końcowym serwera LUMS.

Zastąp:

```text
<CLIENT-TOKEN>
```

tokenem przypisanym do tego klienta.

Ochronij konfigurację:

```bash
sudo chmod 600 \
    /etc/default/lums-agent
```

Sprawdź bez wyświetlania zawartości:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/default/lums-agent
```

Oczekiwane:

```text
600
```

---

# 65. Tokeny klientów

Każdy klient LUMS ma własny token uwierzytelniania.

Token jest używany jako:

```text
Authorization: Bearer <CLIENT-TOKEN>
```

Serwer nie potrzebuje oryginalnej wartości tokena po provisioningu.

Serwer przechowuje kryptograficzną reprezentację tokena do walidacji.

Oznacza to, że poświadczenia klienta powinny być traktowane jak hasła.

Nigdy nie umieszczaj prawdziwego tokena w:

```text
Git
documentation
screenshots
issue reports
shell history
public configuration
```

---

# 66. Provisioning tokena klienta

Utwórz lub provisionuj klienta z interfejsu administratora LUMS zgodnie z bieżącym workflow zarządzania klientami.

Wynikowy token klienta musi zostać przeniesiony do zamierzonego klienta przez bezpieczny kanał.

Przechowuj go tylko w:

```text
/etc/default/lums-agent
```

na kliencie.

Nie używaj ponownie jednego tokena klienta na wielu maszynach.

Zamierzona relacja to:

```text
Client A
    ↓
Token A

Client B
    ↓
Token B

Client C
    ↓
Token C
```

Dlatego skompromitowany token powinien identyfikować tylko powiązanego z nim klienta.

---

# 67. Rotacja tokena klienta

Tokeny klientów mogą być rotowane przez administratora.

Przepływ rotacji to:

```text
Current token
     ↓
Administrator rotates token
     ↓
Old token invalidated
     ↓
New token issued
     ↓
Client configuration updated
```

Po zaktualizowaniu konfiguracji klienta uruchom agenta ręcznie, aby sprawdzić, czy uwierzytelnianie się powiedzie.

Zrotowany token nie może być akceptowany w nieskończoność.

---

# 68. Zaufanie TLS

Agent LUMS komunikuje się z serwerem przez HTTPS.

Weryfikacja certyfikatu musi pozostać włączona.

Dla publicznie zaufanego certyfikatu wystarczy normalny magazyn zaufania systemu operacyjnego.

Dla prywatnego CA laboratoryjnego zainstaluj certyfikat CA na kliencie.

Nie rozwiązuj problemów z certyfikatami przez wyłączanie weryfikacji.

Prawidłowym rozwiązaniem jest sprawienie, aby klient ufał zamierzonemu urzędowi certyfikacji.

---

# 69. Zaufanie TLS w Debian / Ubuntu

W systemach z rodziny Debian prywatne CA można zainstalować w systemowym magazynie zaufania.

Skopiuj certyfikat CA:

```bash
sudo cp \
    lums-ca.crt \
    /usr/local/share/ca-certificates/lums-ca.crt
```

Zaktualizuj magazyn zaufania:

```bash
sudo update-ca-certificates
```

Sprawdź, że certyfikat jest akceptowany:

```bash
curl -I \
    https://LUMS-SERVER/
```

Jeśli polecenie się powiedzie bez `-k`, konfiguracja zaufania systemu działa.

---

# 70. Zaufanie TLS w Arch Linux

W Arch Linux zainstaluj prywatne CA przy użyciu skonfigurowanego mechanizmu magazynu zaufania systemu.

Po zainstalowaniu CA zaktualizuj bazę zaufania zgodnie z aktywną konfiguracją magazynu zaufania.

Sprawdź:

```bash
curl -I \
    https://LUMS-SERVER/
```

Połączenie powinno się powieść bez:

```text
-k
```

Nie konfiguruj trwale agenta tak, aby ignorował weryfikację certyfikatów.

---

# 71. Sprawdzenie menedżera pakietów

Agent wykrywa obsługiwaną rodzinę menedżerów pakietów.

Dla Debian/Ubuntu:

```bash
command -v apt
```

oraz:

```bash
command -v dpkg-query
```

Sprawdź zainstalowane pakiety:

```bash
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n' \
    | head
```

Sprawdź dostępne aktualizacje:

```bash
apt list --upgradable
```

Dla Arch Linux:

```bash
command -v pacman
```

Sprawdź zainstalowane pakiety:

```bash
pacman -Q | head
```

Sprawdź dostępne aktualizacje:

```bash
pacman -Qu
```

Abstrakcja menedżera pakietów automatycznie używa odpowiedniej implementacji.

---

# 72. Sprawdzenie uprawnień agenta

Sprawdź katalog instalacji:

```bash
ls -ld \
    /opt/lums-agent
```

Sprawdź zainstalowane pliki:

```bash
ls -lh \
    /opt/lums-agent/
```

Agent nie potrzebuje dostępu do zapisu w swoim katalogu źródłowym.

Konfiguracja klienta pozostaje chroniona oddzielnie:

```bash
sudo stat -c '%a %U:%G %n' \
    /etc/default/lums-agent
```

Oczekiwane:

```text
600
```

Agent wymaga wystarczających uprawnień systemowych, aby sprawdzić stan pakietów i wykonać operacje na pakietach.

Dokładne uprawnienia środowiska wykonawczego są zdefiniowane przez zainstalowaną usługę systemd.

---

# 73. Sprawdzenie konfiguracji agenta

Przed uruchomieniem usługi sprawdź, czy plik konfiguracji istnieje:

```bash
sudo test -r \
    /etc/default/lums-agent \
    && echo "agent configuration: OK"
```

Nie wyświetlaj zawartości pliku konfiguracji.

Sprawdź, czy wymagane zmienne istnieją bez ujawniania tokena:

```bash
sudo sh -c '
set -a
. /etc/default/lums-agent
set +a

test -n "$LUMS_BASE" &&
echo "LUMS_BASE: configured"

test -n "$LUMS_TOKEN" &&
echo "LUMS_TOKEN: configured"
'
```

Sama wartość tokena nie może być wyświetlana.

---

# 74. Ręczne przetestowanie agenta

Przed włączeniem timera wykonaj agenta raz ręcznie:

```bash
sudo systemctl start \
    lums-agent.service
```

Sprawdź wynik:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Agent to usługa one-shot.

Po pomyślnym zakończeniu może wyświetlić:

```text
Active: inactive (dead)
```

To jest normalne.

Ważnym wynikiem jest:

```text
status=0/SUCCESS
```

Sprawdź journal:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

---

# 75. Sprawdzenie pierwszego raportu klienta

Pomyślne uruchomienie agenta powinno zaraportować klienta do serwera LUMS.

Kompletna ścieżka to:

```text
Agent
   ↓
HTTPS
   ↓
Nginx
   ↓
LUMS API
   ↓
Bearer authentication
   ↓
Client lookup
   ↓
Report accepted
```

W razie potrzeby sprawdź logi serwera:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Klient powinien pojawić się w interfejsie webowym LUMS po pomyślnym raporcie.

Samo pomyślne działanie usługi lokalnej nie jest wystarczające.

Serwer musi zaakceptować raport.

---

# 76. Sprawdzenie klienta w interfejsie webowym

Zaloguj się jako administrator lub operator.

Otwórz przegląd klientów.

Nowy klient powinien zaraportować informacje takie jak:

```text
Hostname
IP address
Operating system
Architecture
Agent version
Last report
Installed packages
Available updates
```

Zaraportowane informacje należą do tego klienta.

Klient nie może uzyskiwać dostępu do zasobów innego klienta.

---

# 77. Włączenie timera raportowania

Dopiero po pomyślnym ręcznym uruchomieniu agenta należy włączyć timer raportowania:

```bash
sudo systemctl enable --now \
    lums-agent.timer
```

Sprawdź:

```bash
sudo systemctl status \
    lums-agent.timer \
    --no-pager
```

Sprawdź harmonogram:

```bash
systemctl list-timers \
    lums-agent.timer \
    --no-pager
```

Timer okresowo uruchamia:

```text
lums-agent.service
```

Sama usługa pozostaje jednostką one-shot.

Dlatego normalne jest, że usługa wraca do:

```text
inactive (dead)
```

między wykonaniami timera.

---

# 78. Sprawdzenie zaplanowanego raportowania

Po włączeniu timera sprawdź następne zaplanowane wykonanie:

```bash
systemctl list-timers \
    --all \
    --no-pager | grep lums-agent
```

Po wykonaniu timera sprawdź:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Sprawdź odpowiedni raport klienta w LUMS.

Zdrowy cykl raportowania to:

```text
Timer
  ↓
Agent service
  ↓
System inventory
  ↓
Package inventory
  ↓
Update detection
  ↓
HTTPS report
  ↓
LUMS database
```

---

# 79. Punkt kontrolny instalacji klienta

Przed zainstalowaniem watchera wykonania sprawdź:

```text
[ ] Supported Linux distribution
[ ] Python 3 available
[ ] systemd available
[ ] Package manager available
[ ] Agent installed
[ ] Agent version verified
[ ] Watcher files installed
[ ] Client configuration exists
[ ] Client token protected
[ ] TLS certificate trusted
[ ] Agent service succeeds
[ ] Client report accepted
[ ] Client visible in LUMS
[ ] Reporting timer enabled
[ ] Scheduled reporting verified
```

Nie przechodź do testowania zadań aktualizacji, dopóki ścieżka raportowania nie działa.

Następna sekcja instaluje i waliduje watcher wykonania.

# 80. Instalacja watchera wykonania

Watcher wykonania LUMS odpowiada za wykrywanie i wykonywanie oczekujących zadań aktualizacji na kliencie.

Architektura oddziela raportowanie od wykonania:

```text
Reporting
    │
    ▼
lums-agent.service
    │
    └── system inventory / update detection

Execution
    │
    ▼
lums-agent-watcher.service
    │
    └── pending update jobs
```

To rozdzielenie pozwala regularnemu raportowaniu klienta kontynuować niezależnie od wykonania aktualizacji.

---

# 81. Sprawdzenie instalacji watchera

Sprawdź, czy watcher jest obecny:

```bash
ls -lh \
    /opt/lums-agent/watcher.py
```

Sprawdź zainstalowaną wersję:

```bash
grep -n \
    'WATCHER_VERSION' \
    /opt/lums-agent/watcher.py
```

Obecna wersja watchera to:

```text
1.2.1
```

---

# 82. Sprawdzenie usługi watchera

Sprawdź jednostkę systemd:

```bash
systemctl cat \
    lums-agent-watcher.service
```

Usługa musi odwoływać się do:

```text
/opt/lums-agent/watcher.py
```

Sprawdź, czy jednostka jest znana systemd:

```bash
systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Usługa może być nieaktywna, gdy nie wywołano żadnego wykonania.

To samo w sobie nie jest błędem.

---

# 83. Sprawdzenie timera watchera

Przed włączeniem timera watchera sprawdź, że:

- `/etc/default/lums-agent` istnieje i zawiera poprawną konfigurację klienta.
- Punkt końcowy serwera LUMS i token klienta są poprawnie skonfigurowane.
- Ręczne uruchomienie agenta powiodło się i serwer zaakceptował raport klienta.
- Oba pliki jednostek watchera zostały zainstalowane z repozytorium.

Nie włączaj timera, gdy uwierzytelnianie lub raportowanie kończy się niepowodzeniem.

Sprawdź timer:

```bash
systemctl cat \
    lums-agent-watcher.timer
```

Włącz timer dopiero po sprawdzeniu wszystkich powyższych warunków wstępnych:

```bash
sudo systemctl enable --now \
    lums-agent-watcher.timer
```

Sprawdź:

```bash
systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

Sprawdź następne zaplanowane wykonanie:

```bash
systemctl list-timers \
    lums-agent-watcher.timer \
    --no-pager
```

---

# 84. Zrozumienie wykonania uwzględniającego bezczynność

Watcher może używać informacji o bezczynności klienta przed wykonaniem zadań aktualizacji.

Zamierzony przepływ to:

```text
Pending job
    │
    ▼
Watcher
    │
    ▼
Idle detection
    │
    ├── idle state available
    │       │
    │       ▼
    │   idle threshold
    │       │
    │       ▼
    │   execute when allowed
    │
    └── idle state unavailable
            │
            ▼
        use configured
        fallback behavior
```

Wykrywanie bezczynności nigdy nie może być interpretowane jako uwierzytelnianie lub autoryzacja.

To wyłącznie mechanizm planowania wykonania.

---

# 85. Sprawdzenie wykrywania bezczynności

Uruchom ścieżkę wykrywania bezczynności ręcznie przez zainstalowaną implementację agenta/watchera.

Sprawdź wynikowy journal usługi:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 100 \
    --no-pager
```

Jeśli platforma nie dostarcza wymaganych informacji o bezczynności, klient może zaraportować wykrywanie bezczynności jako niedostępne.

To nie jest automatycznie awarią.

Ważnym rozróżnieniem jest:

```text
idle_supported = available
```

w porównaniu do:

```text
idle_supported = unavailable
```

Nie można zakładać, że klient jest bezczynny tylko dlatego, że nie zwrócono informacji o bezczynności.

---

# 86. Utworzenie kontrolowanego testowego zadania aktualizacji

Nie rozpoczynaj testów instalacji od dużej aktualizacji systemu.

Do pierwszego testu użyj małego, znanego pakietu.

Pakiet powinien:

```text
exist in the configured repository
be safe to install
be removable again
not be required by the operating system
```

Przykładowy pakiet testowy:

```text
sl
```

Przed utworzeniem zadania sprawdź, czy jest już zainstalowany:

```bash
dpkg-query \
    -W \
    -f='${Status}\n' \
    sl \
    2>/dev/null || true
```

Dla Arch Linux użyj pakietu dostępnego w skonfigurowanych repozytoriach i odpowiedniego do testu odwracalnego.

Nie używaj `sl` na ślepo na każdej dystrybucji.

---

# 87. Sprawdzenie wyszukiwania pakietów

Użyj interfejsu zarządzania pakietami LUMS do wyszukania wybranego pakietu.

Przepływ wyszukiwania to:

```text
Browser
   ↓
LUMS API
   ↓
Package Search Request
   ↓
Client
   ↓
APT / pacman
   ↓
Package Search Result
   ↓
LUMS API
   ↓
Browser
```

Sprawdź, czy wynik zawiera oczekiwane informacje:

```text
Package
Version
Description
Status
Action
```

Dla Arch Linux mogą zostać zwrócone również informacje o repozytorium.

---

# 88. Uprawnienia do zarządzania pakietami

Zarządzanie pakietami jest ograniczone przez RBAC.

Administrator:

```text
Allowed
```

Operator:

```text
Allowed
```

Viewer:

```text
Not allowed
```

Viewer nie może wykonywać instalacji lub usuwania pakietów przez bezpośrednie wywołanie API.

Ukrycie funkcji w interfejsie przeglądarki to tylko dodatkowe ograniczenie użyteczności.

Autoryzacja po stronie serwera to rzeczywista granica bezpieczeństwa.

---

# 89. Test instalacji pakietu

Utwórz zadanie instalacji poprzez interfejs LUMS.

Operacja logiczna to:

```text
INSTALL_PACKAGE
```

Zadanie jest przechowywane w bazie danych LUMS, zanim agent je wykona.

Oczekiwany przepływ to:

```text
Create job
   ↓
PENDING
   ↓
Watcher detects job
   ↓
RUNNING
   ↓
Package manager
   ↓
SUCCESS
```

Monitoruj zadanie w interfejsie LUMS.

Nie modyfikuj ręcznie bazy danych, aby wymusić stan zadania.

---

# 90. Sprawdzenie wyniku instalacji

Po zgłoszeniu sukcesu przez zadanie sprawdź pakiet lokalnie.

W Debian/Ubuntu:

```bash
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n' \
    sl
```

Sprawdź, czy menedżer pakietów się zgadza:

```bash
apt-cache policy \
    sl
```

Pakiet musi być faktycznie zainstalowany.

Stan `SUCCESS` w LUMS musi odpowiadać pomyślnej operacji po stronie klienta.

---

# 91. Sprawdzenie wyniku zadania

Sprawdź historię zadań LUMS.

Sprawdź:

```text
Action
Package
Client
Start time
Completion time
Result
```

Wynik zwrócony przez klienta musi zostać zwalidowany przez serwer.

Nieprawidłowe lub niekompletne dane wyników nie mogą w cichy sposób stać się pomyślnym zadaniem.

Ta walidacja jest częścią modelu bezpieczeństwa i niezawodności LUMS.

---

# 92. Test usuwania pakietu

Po sprawdzeniu instalacji utwórz zadanie usunięcia:

```text
REMOVE_PACKAGE
```

Monitoruj:

```text
PENDING
   ↓
RUNNING
   ↓
SUCCESS
```

Po zakończeniu:

```bash
dpkg-query \
    -W \
    -f='${Status}\n' \
    sl \
    2>/dev/null || true
```

Pakiet nie powinien być już zainstalowany.

Jeśli pakiet nie był zainstalowany przed testem, nie traktuj jego braku jako dowodu pomyślnej operacji usunięcia.

---

# 93. Test aktualizacji pakietu

Aktualizacje pakietów używają:

```text
UPDATE_PACKAGE
```

Serwer sprawdza, czy żądany pakiet jest dostępną aktualizacją przed utworzeniem odpowiedniego zadania.

Ogólny przepływ to:

```text
Client reports available updates
       ↓
User selects package
       ↓
Server validates package
       ↓
Update job created
       ↓
Watcher executes
       ↓
Result reported
```

Nie konstruuj ręcznie żądań aktualizacji, które omijają normalną ścieżkę walidacji.

---

# 94. Test aktualizacji systemu

Kompletna aktualizacja systemu używa:

```text
UPDATE_SYSTEM
```

Ta operacja wpływa na stan menedżera pakietów klienta szerzej niż operacja pojedynczego pakietu.

Dla pierwszego testu aktualizacji systemu:

```text
Use a test client
Use a current backup
Monitor the console
Monitor the LUMS job
Do not interrupt the package manager
```

Nie używaj samego serwera produkcyjnego jako pierwszego celu testu aktualizacji systemu.

---

# 95. Blokady menedżera pakietów

APT i pacman mogą używać blokad menedżera pakietów.

Gdy operacja nie powiedzie się z powodu aktywnego innego procesu zarządzania pakietami, sprawdź działające procesy przed podjęciem działania.

Debian/Ubuntu:

```bash
ps aux | grep -E \
    '[a]pt|[d]pkg|[u]nattended'
```

Arch Linux:

```bash
ps aux | grep -E \
    '[p]acman|[p]ar'
```

Nie usuwaj plików blokad menedżera pakietów, gdy menedżer pakietów faktycznie działa.

Blokada zwykle chroni przed równoczesnymi operacjami na pakietach.

---

# 96. Rozróżnienie awarii LUMS od awarii menedżera pakietów

Gdy zadanie się nie powiedzie, ustal, która warstwa zawiodła.

```text
LUMS API
   │
   ├── Job creation failure
   │
   ▼
LUMS database
   │
   ├── State / persistence problem
   │
   ▼
Watcher
   │
   ├── Execution problem
   │
   ▼
Package manager
   │
   ├── APT / pacman failure
   │
   ▼
Operating system
```

Sprawdź journal klienta:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Sprawdź kontener LUMS:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Nie ponawiaj natychmiast nieudanego zadania bez ustalenia, dlaczego się nie powiodło.

---

# 97. Sprawdzenie punktów kontrolnych zadań

LUMS śledzi stan zadań i elementów pakietów.

Dla zadań opartych na pakietach poszczególne elementy pakietów mogą być checkpointowane.

Zamierzone zachowanie to:

```text
Package A → SUCCESS
Package B → SUCCESS
Package C → RUNNING
             │
             ▼
          interruption
             │
             ▼
          recovery
             │
             ▼
Package A → not repeated
Package B → not repeated
Package C → resumed / handled
```

Zapobiega to niepotrzebnemu powtarzaniu zakończonych operacji na pakietach po przerwie.

---

# 98. Test kontrolowanego wznawiania zadania

Użyj niekrytycznego zadania testowego.

Uruchom zadanie i obserwuj jego stan:

```text
PENDING
```

następnie:

```text
RUNNING
```

Nie przerywaj celowo aktualizacji produkcyjnej.

Do testów wznawiania użyj dedykowanego klienta testowego i kontrolowanej operacji na pakiecie.

Po przerwie lub symulowanej awarii uruchom ponownie watcher:

```bash
sudo systemctl restart \
    lums-agent-watcher.timer
```

Następnie sprawdź:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Sprawdź, czy już pomyślne elementy pakietów nie są niepotrzebnie wykonywane ponownie.

---

# 99. Sprawdzenie wykrywania restartu

Niektóre operacje na pakietach mogą wymagać restartu.

Agent/watcher raportuje wymagania restartu do LUMS.

Ogólny przepływ to:

```text
Package operation
      ↓
Reboot requirement detected
      ↓
Result reported
      ↓
LUMS records reboot state
```

Po operacji testowej, która zgodnie z oczekiwaniami wymaga restartu, sprawdź odpowiedni wynik zadania w interfejsie LUMS.

Nie restartuj klienta produkcyjnego wyłącznie w celu przetestowania mechanizmu, chyba że system jest przeznaczony do tego testu.

---

# 100. Sprawdzenie raportowania po restarcie

Gdy klient testowy zostanie zrestartowany, sprawdź, czy:

```text
systemd
   ↓
LUMS Agent timer
   ↓
Agent report
   ↓
LUMS server
```

nadal działa.

Sprawdź:

```bash
systemctl status \
    lums-agent.timer \
    --no-pager
```

oraz:

```bash
systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

Następnie sprawdź najnowszy raport w interfejsie LUMS.

---

# 101. Sprawdzenie wykrywania aktualizacji

Uruchom agenta ręcznie:

```bash
sudo systemctl start \
    lums-agent.service
```

Sprawdź:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Klient powinien zaraportować:

```text
Installed packages
Available updates
Agent status
```

Serwer powinien zaktualizować bieżący stan klienta.

Nie myl:

```text
available updates
```

z:

```text
installed packages
```

Reprezentują różne zbiory danych.

---

# 102. Sprawdzenie zainstalowanego oprogramowania

Otwórz sekcję zainstalowanego oprogramowania klienta w LUMS.

Lista pakietów powinna odpowiadać menedżerowi pakietów po stronie klienta.

Dla Debian/Ubuntu:

```bash
dpkg-query \
    -W \
    -f='${binary:Package}\t${Version}\n'
```

Dla Arch:

```bash
pacman -Q
```

Inwentarz LUMS ma charakter informacyjny, dopóki zadanie nie zostanie jawnie utworzone.

Filtr zainstalowanych pakietów sam nie modyfikuje klienta.

---

# 103. Sprawdzenie wyszukiwania pakietów osobno

Wyszukiwanie w zarządzaniu pakietami jest oddzielone od filtra zainstalowanych pakietów.

Rozróżnienie to:

```text
Installed Package Filter
    ↓
Searches the package inventory already reported by the client

Package Management Search
    ↓
Requests package information from the client's package manager
```

Nie traktuj obu funkcji wyszukiwania jako wymiennych.

Pakiet może być dostępny poprzez APT lub pacman, ale nie zainstalowany.

---

# 104. Sprawdzenie izolacji pakietów Viewera

Zaloguj się jako Viewer.

Sprawdź, że interfejs zarządzania pakietami nie jest dostępny.

Następnie sprawdź ograniczenie po stronie serwera, próbując nieautoryzowanego żądania zarządzania pakietami przez zatwierdzoną metodę testową.

Żądanie musi zostać odrzucone.

Dostęp Viewera musi pozostać tylko do odczytu.

---

# 105. Sprawdzenie zarządzania pakietami przez operatora

Zaloguj się jako Operator.

Sprawdź dostęp do:

```text
Package Search
Package Installation
Package Removal
Package Updates
Update Jobs
Update History
```

Operator nie może uzyskać dostępu do funkcji zarządzania użytkownikami wyłącznie administracyjnych.

---

# 106. Sprawdzenie zarządzania pakietami przez administratora

Zaloguj się jako Administrator.

Sprawdź te same możliwości zarządzania pakietami co Operator.

Dodatkowo sprawdź dostęp do:

```text
User Management
Client Management
Client Token Rotation
```

Uprawnienia administratora muszą pozostać egzekwowane po stronie serwera.

---

# 107. Pierwszy kompleksowy test pakietu end-to-end

Pierwszy kompletny test zarządzania pakietami powinien przebiegać według tej sekwencji:

```text
1. Client reports successfully
2. Package search succeeds
3. Package result is displayed
4. Administrator/Operator creates INSTALL_PACKAGE job
5. Job becomes PENDING
6. Watcher detects the job
7. Job becomes RUNNING
8. Package manager executes
9. Client reports result
10. Server validates result
11. Job becomes SUCCESS
12. Installed package is verified locally
13. Package is visible in LUMS inventory
```

Dopiero po pomyślnym przejściu tej sekwencji należy rozpocząć szersze testy aktualizacji.

---

# 108. Punkt kontrolny wykonania po stronie klienta

Sprawdź:

```text
[ ] Watcher installed
[ ] Watcher version verified
[ ] Watcher timer enabled
[ ] Idle detection works or reports unavailable correctly
[ ] Package search works
[ ] Package installation works
[ ] Package removal works
[ ] Package update works
[ ] System update path is available
[ ] Job states transition correctly
[ ] Job results are validated
[ ] Package checkpointing works
[ ] Reboot detection works
[ ] Reporting continues after reboot
[ ] Viewer cannot mutate package state
[ ] Operator can manage packages
[ ] Administrator can manage packages
```

W tym momencie podstawowa ścieżka wykonania klienta LUMS jest zainstalowana i zwalidowana.

Następna sekcja obejmuje pełną walidację end-to-end, weryfikację RBAC, kopię zapasową/przywracanie, konserwację, aktualizacje i końcowe kontrole instalacji.

# 109. Pełna walidacja end-to-end

Po skonfigurowaniu serwera i co najmniej jednego klienta Linuksa wykonaj kompletną walidację end-to-end.

Kompletna ścieżka LUMS to:

```text
Browser
   │
   ▼
Nginx / HTTPS
   │
   ▼
LUMS API
   │
   ▼
SQLite
   │
   ▼
Client Agent
   │
   ▼
Package Manager
   │
   ▼
Update Result
   │
   ▼
SQLite
   │
   ▼
Web Interface
```

Nie uznawaj instalacji za kompletną tylko dlatego, że interfejs webowy się otwiera.

Wszystkie główne warstwy muszą zostać zweryfikowane.

---

# 110. Kontrola stanu serwera

Sprawdź kontener LUMS:

```bash
sudo docker ps \
    --filter name=lums
```

Sprawdź stan kontenera:

```bash
sudo docker inspect \
    lums \
    --format '{{.State.Status}}'
```

Oczekiwane:

```text
running
```

Sprawdź ostatnie logi:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Logi nie powinny zawierać aktywnej awarii uruchamiania lub migracji.

---

# 111. Kontrola bezpieczeństwa kontenera

Sprawdź konfigurację bezpieczeństwa środowiska wykonawczego:

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'
```

Oczekiwana podstawa:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

Sprawdź powiązanie sieciowe:

```bash
sudo docker port \
    lums
```

Oczekiwane:

```text
5000/tcp -> 127.0.0.1:5050
```

---

# 112. Kontrola trwałego przechowywania

Sprawdź wolumen LUMS:

```bash
sudo docker volume inspect \
    lums-data
```

Sprawdź, czy baza danych aplikacji istnieje:

```bash
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db
```

Baza danych musi znajdować się w trwałym przechowywaniu.

Nie przechowuj bazy danych produkcyjnej wyłącznie w systemie plików kontenera.

---

# 113. Kontrola stanu SQLite

Sprawdź bieżącą konfigurację środowiska wykonawczego SQLite:

```bash
sudo docker exec -i lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

for name in (
    "journal_mode",
    "busy_timeout",
    "synchronous",
    "foreign_keys",
):
    value = db.execute(
        f"PRAGMA {name}"
    ).fetchone()[0]
    print(f"{name}={value}")

db.close()
PY
```

Obecna podstawa to:

```text
journal_mode=wal
busy_timeout=5000
synchronous=2
foreign_keys=0
```

Aplikacja jawnie włącza wymuszanie kluczy obcych.

---

# 114. Kontrola integralności SQLite

Uruchom:

```bash
sudo docker exec -i lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

result = db.execute(
    "PRAGMA integrity_check"
).fetchone()[0]

print(result)

db.close()
PY
```

Oczekiwane:

```text
ok
```

Nie kontynuuj nowego wdrożenia produkcyjnego, jeśli kontrola integralności zgłasza uszkodzenie.

---

# 115. Sprawdzenie migracji bazy danych

Sprawdź stan migracji:

```bash
sudo docker logs \
    --tail 200 \
    lums | grep -i migration
```

Aplikacja musi ukończyć skonfigurowane migracje przed normalnym działaniem.

Nie modyfikuj ręcznie tabeli stanu migracji, chyba że bieżąca procedura migracji LUMS wyraźnie tego wymaga.

---

# 116. Uruchomienie automatycznego zestawu testów

W środowisku rozwojowym/testowym LUMS:

```bash
cd /opt/lums-public
```

Uruchom:

```bash
./.venv-test/bin/pytest -q
```

Liczba testów zmienia się w miarę rozwoju projektu; polegaj na wyniku polecenia, a nie na stałej liczbie w tym dokumencie.

Ważnym wymogiem jest:

```text
all tests pass
```

Nie ignoruj niepowodzeń testów tylko dlatego, że produkcyjny interfejs webowy wydaje się funkcjonalny.

---

# 117. Sprawdzenie RBAC

Obecny model ról to:

| Funkcja                | Administrator | Operator | Viewer |
| ---------------------- | ------------: | -------: | -----: |
| Przeglądanie klientów  |           Tak |      Tak |    Tak |
| Zainstalowane oprogramowanie |     Tak |      Tak |    Tak |
| Dostępne aktualizacje  |           Tak |      Tak |     Nie |
| Tworzenie/wykonanie zadań |       Tak |      Tak |     Nie |
| Historia aktualizacji  |           Tak |      Tak |     Nie |
| Zarządzanie pakietami  |           Tak |      Tak |     Nie |
| Konserwacja systemu    |           Tak |      Tak |     Nie |
| Tworzenie/wyłączanie klientów |   Tak |       Nie |     Nie |
| Rotacja tokenów klientów |         Tak |       Nie |     Nie |
| Zarządzanie użytkownikami |        Tak |       Nie |     Nie |
| Zarządzanie rolami     |           Tak |       Nie |     Nie |

Interfejs powinien odzwierciedlać te uprawnienia.

Co ważniejsze, API musi je egzekwować niezależnie.

---

# 118. Sprawdzenie dostępu administratora

Zaloguj się jako Administrator.

Sprawdź dostęp do:

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
User management
```

Sprawdź funkcje zarządzania klientami:

```text
Create client
Disable client
Rotate client token
```

Administrator powinien móc wykonać te operacje.

---

# 119. Sprawdzenie dostępu operatora

Zaloguj się jako Operator.

Sprawdź dostęp do:

```text
Clients
Installed software
Available updates
Update jobs
Update history
Package management
System maintenance
```

Sprawdź, że funkcjonalność wyłącznie administracyjna jest niedostępna:

```text
User management
Role management
Client creation/disabling
Client-token rotation
```

Nie polegaj wyłącznie na ukrytych elementach UI.

Chronione operacje API muszą odrzucać nieautoryzowane żądania.

---

# 120. Sprawdzenie dostępu Viewera

Zaloguj się jako Viewer.

Viewer powinien mieć dostęp do:

```text
Clients
Installed software
```

Następujące nie może być dostępne:

```text
Available updates
Update jobs
Update history
Package management
System maintenance
```

Viewer nie może modyfikować stanu klienta.

---

# 121. Sprawdzenie uwierzytelniania klienta

Potwierdź, że każdy klient używa własnego tokena Bearer.

Oczekiwany model to:

```text
Client A → Token A
Client B → Token B
Client C → Token C
```

Nie udostępniaj tokenów między klientami.

Sprawdź, że zrotowany lub unieważniony token nie jest już akceptowany.

Nigdy nie umieszczaj prawdziwych tokenów w wynikach testów ani dokumentacji.

---

# 122. Sprawdzenie wykrywania aktualizacji

Na kliencie testowym:

```bash
sudo systemctl start \
    lums-agent.service
```

Sprawdź:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Następnie sprawdź klienta w interfejsie LUMS.

Zaraportowane informacje powinny zawierać bieżący inwentarz pakietów i informacje o aktualizacjach, gdzie to obsługiwane.

---

# 123. Sprawdzenie tworzenia zadań aktualizacji

Utwórz kontrolowane zadanie aktualizacji poprzez interfejs LUMS.

Zadanie powinno początkowo pojawić się jako:

```text
PENDING
```

Watcher następnie przetwarza zadanie:

```text
PENDING
   ↓
RUNNING
   ↓
SUCCESS
```

lub:

```text
PENDING
   ↓
RUNNING
   ↓
FAILED
```

w zależności od rzeczywistego wyniku operacji.

Nie zmieniaj ręcznie stanu bazy danych.

---

# 124. Sprawdzenie wykonania zadania

Sprawdź watcher klienta:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Sprawdź serwer LUMS:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Porównaj stan zadania po stronie serwera z wynikiem wykonania po stronie klienta.

Oba muszą się zgadzać.

---

# 125. Sprawdzenie walidacji wyników pakietów

Zadanie nie może stać się pomyślne tylko dlatego, że klient przesłał składniowo poprawną odpowiedź.

Serwer waliduje zwrócony wynik.

Sprawdź to poprzez automatyczne testy walidacji wyników:

```bash
./.venv-test/bin/pytest -q \
    tests/test_job_result.py
```

Pomyślny wynik musi zawierać oczekiwaną strukturę i poprawny kontekst zadania.

Źle sformułowane lub niespójne wyniki muszą zostać odrzucone.

---

# 126. Sprawdzenie wznawiania zadania

Użyj dedykowanego klienta testowego do testów wznawiania.

Model wznawiania to:

```text
Job
 │
 ├── package item A → SUCCESS
 ├── package item B → SUCCESS
 └── package item C → interrupted
                       │
                       ▼
                    recovery
                       │
                       ▼
                  resume safely
```

Po wznowieniu poprzednio pomyślne elementy pakietów nie mogą być niepotrzebnie powtarzane.

Sprawdź:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Następnie sprawdź końcowy stan zadania w LUMS.

---

# 127. Sprawdzenie wykrywania restartu

Dla kontrolowanej aktualizacji testowej wymagającej restartu sprawdź, czy klient raportuje wymaganie restartu.

Po restarcie:

```bash
systemctl status \
    lums-agent.timer \
    --no-pager
```

oraz:

```bash
systemctl status \
    lums-agent-watcher.timer \
    --no-pager
```

Klient musi wznowić normalne raportowanie po rozruchu.

---

# 128. Sprawdzenie rejestrowania audytu

Wykonaj kontrolowane działanie administracyjne, a następnie sprawdź dziennik audytu LUMS.

Odpowiednie operacje obejmują:

```text
Login
User creation
Client creation
Client-token rotation
Job creation
Package management
```

Wpisy audytu powinny dostarczać wystarczających informacji do odtworzenia działania administracyjnego bez ujawniania sekretów.

Nie rejestruj:

```text
Passwords
Client tokens
Application secrets
Private keys
Session secrets
```

---

# 129. Sprawdzenie redakcji logów

Sprawdź ostatnie logi:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Sprawdź logi klienta:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

oraz:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Poświadczenia uwierzytelniania i sekrety nie mogą pojawiać się w normalnym wyjściu diagnostycznym.

Jeśli polecenie diagnostyczne ujawniłoby sekret, nie wklejaj jego wyjścia do zgłoszenia, commita ani dokumentacji.

---

# 130. Sprawdzenie ekspozycji sieciowej

Sprawdź porty nasłuchujące:

```bash
sudo ss -lntp
```

Port aplikacji LUMS powinien pozostać:

```text
127.0.0.1:5050
```

Nginx zapewnia usługę zewnętrzną:

```text
:80
:443
```

Aplikacja nie może być bezpośrednio udostępniana przez:

```text
0.0.0.0:5050
```

lub:

```text
0.0.0.0:5000
```

---

# 131. Sprawdzenie konfiguracji zapory sieciowej

Jeśli zapora hosta jest włączona, sprawdź ją:

```bash
sudo ufw status verbose
```

Wdrożenie powinno udostępniać tylko usługi wymagane przez host.

Nie twórz reguły zapory dla portu `5050` tylko dlatego, że Docker używa tego portu wewnętrznie.

Zamierzona architektura to:

```text
LAN
 │
 ▼
443
 │
 ▼
Nginx
 │
 ▼
127.0.0.1:5050
 │
 ▼
LUMS
```

---

# 132. Strategia kopii zapasowych

Baza danych SQLite LUMS to trwały stan aplikacji.

Co najmniej kopie zapasowe powinny chronić:

```text
LUMS database
TLS material
LUMS application secret
Deployment configuration
```

Kopie zapasowe muszą być przechowywane poza aktywnym kontenerem LUMS.

Nie przechowuj kopii zapasowych w:

```text
/app
```

ani nie polegaj na systemie plików kontenera.

Wolumen Docker:

```text
lums-data
```

zawiera trwałe dane aplikacji, ale wolumen Docker sam w sobie nie jest kopią zapasową.

---

# 133. Kopia zapasowa bazy danych

Przed wykonaniem kopii zapasowej bazy danych zidentyfikuj plik bazy danych:

```bash
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db
```

Kopię zapasową bazy danych należy wykonać przy użyciu spójnego mechanizmu kopii zapasowej SQLite.

Nie kopiuj na ślepo aktywnej bazy danych SQLite, gdy jest modyfikowana, jeśli procedura kopii zapasowej nie może zagwarantować spójności.

Po utworzeniu kopii zapasowej sprawdź, czy plik kopii zapasowej istnieje i jest chroniony.

---

# 134. Kopia zapasowa konfiguracji

Ochronij następujący materiał wdrożeniowy:

```text
/etc/lums/secrets/
/etc/lums/tls/
/etc/nginx/sites-available/lums
/etc/nginx/sites-enabled/lums
```

Nie publikuj tych plików.

Następujące pliki są szczególnie wrażliwe:

```text
/etc/lums/secrets/lums_secret
/etc/lums/tls/lums.key
```

Odpowiednio chroń uprawnienia kopii zapasowych.

---

# 135. Planowanie przywracania

Przywracanie należy przetestować w systemie nieprodukcyjnym, zanim będzie potrzebne do odzyskiwania po awarii.

Sekwencja przywracania koncepcyjnie to:

```text
Backup
  ↓
Verify backup integrity
  ↓
Prepare clean LUMS host
  ↓
Restore secret/configuration
  ↓
Restore database
  ↓
Restore TLS material
  ↓
Start LUMS
  ↓
Run integrity checks
  ↓
Validate users/clients/jobs
```

Nie nadpisuj bazy danych produkcyjnej bez uprzedniego zachowania istniejącego stanu.

---

# 136. Sprawdzenie przywrócenia bazy danych

Po przywróceniu bazy danych uruchom:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")

print(
    db.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]
)

db.close()
PY
```

Oczekiwane:

```text
ok
```

Następnie sprawdź:

```text
users
clients
update jobs
package data
audit data
```

Nie zakładaj, że pomyślna kontrola integralności SQLite dowodzi, że pełny stan aplikacji jest poprawny.

---

# 137. Zasady konserwacji

Rutynowa konserwacja powinna przebiegać według:

```text
Observe
   ↓
Back up
   ↓
Change
   ↓
Verify
```

Nie wykonuj niepowiązanej konserwacji podczas aktywnego zadania aktualizacji.

Przed konserwacją:

```bash
sudo docker ps \
    --filter name=lums
```

Sprawdź aktywne zadania w interfejsie LUMS.

Jeśli aktualizacja jest w toku, pozwól jej się zakończyć, chyba że operacja konserwacyjna wyraźnie wymaga przerwy.

---

# 138. Konserwacja kontenera

Sprawdź działający obraz:

```bash
sudo docker inspect \
    lums \
    --format '{{.Config.Image}}'
```

Sprawdź kontener:

```bash
sudo docker ps \
    --filter name=lums
```

Sprawdź ostatnie logi:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Nie usuwaj trwałego wolumenu podczas zwykłej konserwacji kontenera.

Wolumen zawiera stan aplikacji.

---

# 139. Konserwacja obrazu

Przed zastąpieniem obrazu produkcyjnego:

```bash
cd /opt/lums-public
```

Uruchom testy automatyczne:

```bash
./.venv-test/bin/pytest -q
```

Zbuduj nowy obraz:

```bash
sudo docker build \
    -t lums:new \
    .
```

Nie zastępuj działającego kontenera, dopóki obraz nie przejdzie wymaganej walidacji.

Utrzymuj obecnie działający kontener jako dostępny, dopóki zamiennik nie zostanie zweryfikowany.

---

# 140. Kontrolowane zastąpienie kontenera

Podczas zastępowania kontenera produkcyjnego:

```text
Current container
       │
       ▼
Backup / checkpoint
       │
       ▼
Build new image
       │
       ▼
Validate image
       │
       ▼
Stop old container
       │
       ▼
Start new container
       │
       ▼
Validate runtime
       │
       ▼
Validate HTTPS
       │
       ▼
Validate application
```

Trwały wolumen musi pozostać:

```text
lums-data
```

Montaż sekretu musi pozostać tylko do odczytu.

Port aplikacji musi pozostać ograniczony do localhost.

---

# 141. Sprawdzenie bezpieczeństwa środowiska wykonawczego po zastąpieniu

Po każdym zastąpieniu kontenera powtórz:

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'
```

Sprawdź:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

Sprawdź również:

```bash
sudo docker port \
    lums
```

Oczekiwane:

```text
5000/tcp -> 127.0.0.1:5050
```

---

# 142. Sprawdzenie trwałych danych po zastąpieniu

Po uruchomieniu kontenera zastępczego:

```bash
sudo docker exec \
    lums \
    ls -lh /var/lib/lums/lums.db
```

Następnie:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
db.close()
PY
```

Oczekiwane:

```text
ok
```

Na koniec sprawdź przez interfejs LUMS, czy istniejący użytkownicy i klienci są nadal obecni.

---

# 143. Punkt kontrolny zakończenia konserwacji

Po konserwacji sprawdź:

```text
[ ] Container running
[ ] Runtime hardening intact
[ ] Persistent volume mounted
[ ] Database accessible
[ ] SQLite integrity check passes
[ ] Nginx running
[ ] HTTPS working
[ ] Login working
[ ] Existing users present
[ ] Existing clients present
[ ] Agent reporting working
[ ] Watcher working
[ ] Update jobs working
[ ] Audit logging working
```

Dopiero po tych kontrolach operacja konserwacji jest zakończona.

---

# 144. Stan instalacji na tym etapie

Prawidłowo zainstalowane środowisko LUMS składa się teraz z:

```text
                    ┌──────────────────────┐
                    │       Browser        │
                    └──────────┬───────────┘
                               │ HTTPS
                               ▼
                    ┌──────────────────────┐
                    │        Nginx         │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    LUMS Container    │
                    │                      │
                    │ Flask / Gunicorn     │
                    │ RBAC                 │
                    │ CSRF                 │
                    │ Audit Logging        │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │       SQLite         │
                    │     lums-data        │
                    └──────────┬───────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
                ▼                             ▼
        ┌──────────────┐              ┌──────────────┐
        │ LUMS Agent   │              │ LUMS Watcher │
        │ 1.7.0        │              │ 1.2.1        │
        └──────┬───────┘              └──────┬───────┘
               │                             │
               ▼                             ▼
        Inventory / Report             Update Jobs
               │                             │
               └──────────────┬──────────────┘
                              ▼
                       APT / pacman
```

To jest zamierzona architektura operacyjna.

Następna sekcja obejmuje aktualizacje, odinstalowanie i końcową listę kontrolną instalacji.

# 145. Procedura aktualizacji

Aktualizacje LUMS powinny być wykonywane w kontrolowanych krokach.

Zalecana sekwencja to:

```text
Review
   ↓
Backup
   ↓
Test
   ↓
Build
   ↓
Deploy
   ↓
Validate
```

Nie aktualizuj instalacji produkcyjnej tylko dlatego, że istnieje nowa rewizja Git.

Najpierw przejrzyj zmiany:

```bash
cd /opt/lums-public

git status
git log --oneline -10
```

Przejrzyj odpowiednie zmiany aplikacji, agenta i migracji przed wdrożeniem.

---

# 146. Utworzenie kopii zapasowej przed aktualizacją

Przed zastąpieniem kontenera produkcyjnego utwórz bieżącą kopię zapasową trwałego stanu LUMS.

Sprawdź aktywny wolumen:

```bash
sudo docker inspect \
    lums \
    --format '{{json .Mounts}}'
```

Potwierdź, że:

```text
lums-data
```

jest nadal zamontowany w:

```text
/var/lib/lums
```

Ochronij również konfigurację zewnętrzną:

```text
/etc/lums/secrets/
/etc/lums/tls/
/etc/nginx/
```

Nie kontynuuj aktualizacji, jeśli wymaganej kopii zapasowej nie można zweryfikować.

---

# 147. Zatrzymanie niepotrzebnych zmian podczas aktualizacji

Przed aktualizacją sprawdź aktywne zadania w interfejsie LUMS.

Unikaj zastępowania aplikacji, gdy krytyczne zadanie aktualizacji jest aktywnie wykonywane.

W razie potrzeby poczekaj, aż zadanie osiągnie stan końcowy:

```text
SUCCESS
```

lub:

```text
FAILED
```

Nie zmieniaj ręcznie zadania z `RUNNING` na `SUCCESS` lub `FAILED` tylko po to, aby umożliwić aktualizację.

---

# 148. Aktualizacja repozytorium

Przejdź do repozytorium:

```bash
cd /opt/lums-public
```

Sprawdź bieżący stan:

```bash
git status
```

Zaktualizuj repozytorium przy użyciu normalnego workflow projektu.

Po aktualizacji:

```bash
git log --oneline -5
```

Sprawdź, czy wyewidencjonowano zamierzoną rewizję.

Nie wdrażaj repozytorium zawierającego niezamierzone lokalne modyfikacje.

Jeśli obecne są lokalne zmiany:

```bash
git status
```

Przejrzyj je przed kontynuowaniem.

---

# 149. Uruchomienie zestawu testów przed zbudowaniem

Uruchom:

```bash
./.venv-test/bin/pytest -q
```

Wszystkie testy muszą przejść.

Zmieniona liczba testów nie jest automatycznie problemem. Wymogiem jest, aby cały zestaw zakończył się pomyślnie.

---

# 150. Zbudowanie zaktualizowanego obrazu

Zbuduj nowy obraz bez natychmiastowego zastępowania działającego kontenera:

```bash
sudo docker build \
    -t lums:new \
    .
```

Sprawdź obraz:

```bash
sudo docker image inspect \
    lums:new
```

Budowanie musi się pomyślnie zakończyć.

Nie używaj nieudanego lub częściowo zbudowanego obrazu do wdrożenia produkcyjnego.

---

# 151. Sprawdzenie zaktualizowanego obrazu

Przejrzyj metadane obrazu:

```bash
sudo docker image inspect \
    lums:new \
    --format '
User={{.Config.User}}
Entrypoint={{json .Config.Entrypoint}}
Cmd={{json .Config.Cmd}}
'
```

Obraz musi zachować oczekiwany model aplikacji niebędącej rootem.

Środowisko wykonawcze produkcji musi nadal zapewniać:

```text
read-only root filesystem
dropped Linux capabilities
no-new-privileges
read-only secret mount
persistent application volume
localhost-only application port
```

---

# 152. Zastąpienie kontenera produkcyjnego

Gdy nowy obraz przeszedł walidację, zastąp działający kontener przy użyciu ustalonej utwardzonej konfiguracji.

Zatrzymaj istniejący kontener:

```bash
sudo docker stop \
    lums
```

Usuń tylko kontener:

```bash
sudo docker rm \
    lums
```

**Nie** usuwaj:

```text
lums-data
```

Uruchom zamiennik z utwardzonym środowiskiem wykonawczym:

```bash
sudo docker run -d \
    --name lums \
    --restart unless-stopped \
    --read-only \
    --cap-drop=ALL \
    --security-opt=no-new-privileges:true \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --tmpfs /run:rw,noexec,nosuid,size=16m \
    -p 127.0.0.1:5050:5000 \
    -v /etc/lums/secrets/lums_secret:/run/secrets/lums_secret:ro \
    -v lums-data:/var/lib/lums \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    lums:new
```

---

# 153. Sprawdzenie kontenera zastępczego

Sprawdź:

```bash
sudo docker ps \
    --filter name=lums
```

Następnie:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Sprawdź środowisko wykonawcze:

```bash
sudo docker inspect lums \
    --format '
User={{.Config.User}}
ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}}
Privileged={{.HostConfig.Privileged}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
'
```

Oczekiwane:

```text
User=lums
ReadonlyRootfs=true
Privileged=false
CapDrop=["ALL"]
SecurityOpt=["no-new-privileges:true"]
```

---

# 154. Sprawdzenie dostępności aplikacji

Sprawdź lokalny punkt końcowy aplikacji:

```bash
curl -I \
    http://127.0.0.1:5050/
```

Następnie przetestuj publiczną ścieżkę HTTPS:

```bash
curl -I \
    https://LUMS-SERVER/
```

Sprawdź logowanie przez przeglądarkę.

Nie uznawaj aktualizacji za kompletną, dopóki zewnętrzna ścieżka HTTPS również nie została przetestowana.

---

# 155. Sprawdzenie trwałego stanu po aktualizacji

Sprawdź bazę danych:

```bash
sudo docker exec lums \
    ls -lh /var/lib/lums/lums.db
```

Uruchom:

```bash
sudo docker exec lums \
    python3 - <<'PY'
import sqlite3

db = sqlite3.connect("/var/lib/lums/lums.db")
print(db.execute("PRAGMA integrity_check").fetchone()[0])
db.close()
PY
```

Oczekiwane:

```text
ok
```

Sprawdź przez interfejs webowy, że:

```text
users
clients
jobs
audit history
package information
```

pozostają dostępne.

---

# 156. Sprawdzenie komunikacji klienta po aktualizacji

Uruchom agenta na kliencie testowym:

```bash
sudo systemctl start \
    lums-agent.service
```

Sprawdź:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Sprawdź, że serwer akceptuje raport.

Następnie sprawdź klienta w interfejsie LUMS.

---

# 157. Sprawdzenie wykonania aktualizacji po aktualizacji

Utwórz kontrolowane zadanie testowe.

Sprawdź:

```text
PENDING
   ↓
RUNNING
   ↓
SUCCESS
```

lub oczekiwany stan:

```text
FAILED
```

gdy operacja rzeczywiście zawiedzie.

Sprawdź watcher:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

To potwierdza, że aktualizacja nie zepsuła ścieżki wykonania.

---

# 158. Sprawdzenie podstawy bezpieczeństwa po aktualizacji

Każda aktualizacja produkcyjna musi zachować podstawę bezpieczeństwa.

Sprawdź:

```text
[ ] HTTPS
[ ] Bearer client authentication
[ ] RBAC
[ ] CSRF protection
[ ] Audit logging
[ ] Non-root container
[ ] Read-only root filesystem
[ ] Capabilities dropped
[ ] no-new-privileges
[ ] Protected secret mount
[ ] Persistent data volume
[ ] Localhost-only Docker port
[ ] Firewall policy
```

Funkcjonalna aktualizacja, która osłabia te właściwości, nie jest uważana za kompletną.

---

# 159. Procedura wycofania

Jeśli nowy kontener nie przejdzie walidacji, nie niszcz natychmiast informacji o poprzednim wdrożeniu.

Najpierw sprawdź:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Jeśli poprzedni obraz jest nadal dostępny:

```bash
sudo docker images
```

przywróć poprzednio zwalidowany obraz przy użyciu tej samej utwardzonej konfiguracji kontenera.

Trwały wolumen pozostaje:

```text
lums-data
```

Nie przywracaj kopii zapasowej bazy danych tylko dlatego, że kontener aplikacji został zastąpiony.

Przywróć bazę danych tylko wtedy, gdy sama baza danych musi zostać odzyskana.

---

# 160. Przygotowanie do odinstalowania

Przed odinstalowaniem LUMS zdecyduj, czy trwałe dane aplikacji muszą zostać zachowane.

Następujące są oddzielnymi zasobami:

```text
Container
Image
Persistent volume
Configuration
TLS material
Nginx configuration
Client installations
```

Usunięcie kontenera nie usuwa wolumenu Docker.

To rozróżnienie jest celowe.

---

# 161. Usunięcie kontenera LUMS

Zatrzymaj kontener:

```bash
sudo docker stop \
    lums
```

Usuń go:

```bash
sudo docker rm \
    lums
```

Sprawdź:

```bash
sudo docker ps -a \
    --filter name=lums
```

Trwały wolumen jest nadal obecny, chyba że został jawnie usunięty.

---

# 162. Usunięcie obrazu Docker LUMS

Wylistuj obrazy:

```bash
sudo docker images \
    'lums*'
```

Usuń tylko obrazy, które nie są już wymagane:

```bash
sudo docker rmi \
    lums:new
```

Powtórz dla innych przestarzałych lokalnych obrazów LUMS, gdzie to stosowne.

Nie usuwaj obrazu aktualnie wymaganego do wycofania, zanim instalacja nie zostanie całkowicie wycofana z eksploatacji.

---

# 163. Usunięcie trwałego wolumenu

Wykonaj ten krok tylko wtedy, gdy baza danych LUMS nie jest już wymagana.

Sprawdź:

```bash
sudo docker volume inspect \
    lums-data
```

W razie potrzeby utwórz końcową kopię zapasową.

Następnie usuń:

```bash
sudo docker volume rm \
    lums-data
```

To trwale usuwa trwałe dane aplikacji przechowywane w tym wolumenie.

Nie uruchamiaj tego polecenia podczas normalnych aktualizacji.

---

# 164. Usunięcie konfiguracji serwera LUMS

Gdy serwer jest trwale wycofywany z eksploatacji, usuń konfigurację specyficzną dla LUMS:

```text
/etc/lums/
/etc/nginx/sites-available/lums
/etc/nginx/sites-enabled/lums
```

Usuń witrynę Nginx:

```bash
sudo rm -f \
    /etc/nginx/sites-enabled/lums
```

Usuń konfigurację:

```bash
sudo rm -f \
    /etc/nginx/sites-available/lums
```

Następnie zwaliduj Nginx:

```bash
sudo nginx -t
```

Przeładuj:

```bash
sudo systemctl reload nginx
```

Usuń `/etc/lums/` dopiero po sprawdzeniu, że żadna inna aplikacja od niego nie zależy.

---

# 165. Usunięcie instalacji klientów

Klienci LUMS muszą zostać wycofani oddzielnie.

Wyłącz timer agenta:

```bash
sudo systemctl disable --now \
    lums-agent.timer
```

Wyłącz timer watchera:

```bash
sudo systemctl disable --now \
    lums-agent-watcher.timer
```

Zatrzymaj wszelkie pozostałe usługi:

```bash
sudo systemctl stop \
    lums-agent.service \
    lums-agent-watcher.service
```

Usuń zainstalowane jednostki systemd:

```bash
sudo rm -f \
    /etc/systemd/system/lums-agent.service \
    /etc/systemd/system/lums-agent-watcher.service \
    /etc/systemd/system/lums-agent.timer \
    /etc/systemd/system/lums-agent-watcher.timer
```

Przeładuj systemd:

```bash
sudo systemctl daemon-reload
```

Usuń instalację agenta:

```bash
sudo rm -rf \
    /opt/lums-agent
```

Usuń konfigurację klienta:

```bash
sudo rm -f \
    /etc/default/lums-agent
```

Wykonaj te kroki tylko wtedy, gdy klient jest rzeczywiście usuwany z zarządzania LUMS.

---

# 166. Końcowa lista kontrolna instalacji serwera

Ukończona instalacja LUMS powinna spełniać wszystkie następujące warunki:

```text
SERVER
[ ] Debian/Linux host prepared
[ ] Docker installed
[ ] Nginx installed
[ ] Repository deployed
[ ] Application secret generated
[ ] TLS material installed
[ ] LUMS image built
[ ] Persistent volume created
[ ] Hardened container deployed
[ ] Container runs as non-root
[ ] Root filesystem is read-only
[ ] Linux capabilities dropped
[ ] no-new-privileges enabled
[ ] Secret mounted read-only
[ ] Persistent data volume mounted
[ ] Application bound to 127.0.0.1:5050
[ ] Nginx HTTPS configured
[ ] HTTP redirects to HTTPS
[ ] TLS verified
[ ] Database initialized
[ ] SQLite integrity check passes
[ ] Migrations complete
```

---

# 167. Końcowa lista kontrolna instalacji klienta

```text
CLIENT
[ ] Supported Linux distribution
[ ] systemd available
[ ] Agent installed
[ ] Agent version verified
[ ] Watcher installed
[ ] Watcher version verified
[ ] Client configuration protected
[ ] Unique client token configured
[ ] TLS trust configured
[ ] Agent manual run succeeds
[ ] Initial report accepted
[ ] Client visible in LUMS
[ ] Reporting timer enabled
[ ] Watcher timer enabled
[ ] Idle detection verified
[ ] Package inventory verified
[ ] Update detection verified
```

---

# 168. Końcowa lista kontrolna funkcjonalności

```text
FUNCTIONALITY
[ ] Administrator login works
[ ] Operator login works
[ ] Viewer login works
[ ] Administrator RBAC verified
[ ] Operator RBAC verified
[ ] Viewer RBAC verified
[ ] Client authentication verified
[ ] Token rotation verified
[ ] Package search verified
[ ] Package installation verified
[ ] Package removal verified
[ ] Package update verified
[ ] System update path verified
[ ] Update jobs verified
[ ] Job result validation verified
[ ] Job recovery verified
[ ] Reboot detection verified
[ ] Audit logging verified
[ ] Logs contain no secrets
[ ] End-to-end reporting verified
[ ] End-to-end update execution verified
```

---

# 169. Końcowa lista kontrolna bezpieczeństwa

```text
SECURITY
[ ] HTTPS enforced
[ ] Client Bearer authentication enabled
[ ] RBAC enforced server-side
[ ] CSRF protection enabled
[ ] Session protection enabled
[ ] Login rate limiting enabled
[ ] Password hashing enabled
[ ] Client token hashing enabled
[ ] Client token rotation available
[ ] Audit logging enabled
[ ] Secrets outside Git
[ ] Secrets outside Docker image
[ ] TLS private key protected
[ ] Docker root filesystem read-only
[ ] Linux capabilities dropped
[ ] no-new-privileges enabled
[ ] Container runs as non-root
[ ] Persistent data isolated in volume
[ ] Application port localhost-only
[ ] Firewall reviewed
[ ] Default Nginx site removed or controlled
[ ] Backup procedure defined
[ ] Restore procedure tested
```

---

# 170. Końcowa lista kontrolna testów

Uruchom kompletny automatyczny zestaw testów:

```bash
cd /opt/lums-public

./.venv-test/bin/pytest -q
```

Instalację należy uznać za kompletną tylko wtedy, gdy cały zestaw testów przejdzie pomyślnie.

Następnie sprawdź ręcznie środowisko wykonawcze produkcji:

```bash
sudo docker ps \
    --filter name=lums
```

```bash
sudo docker logs \
    --tail 100 \
    lums
```

```bash
curl -I \
    https://LUMS-SERVER/
```

```bash
sudo ss -lntp
```

---

# 171. Końcowa kontrola dokumentacji

Przed ogłoszeniem instalacji kompletnej sprawdź, czy dokumentacja pasuje do rzeczywistego wdrożenia.

Co najmniej przejrzyj:

```text
install.md
security.md
troubleshooting.md
administration.md
docs/README.md
```

Techniczne przewodniki na poziomie głównym są angielskim źródłem prawdy. Zlokalizowane przewodniki w `docs/locales/` to zwięzłe przewodniki dla początkujących, a nie kopie słowo w słowo każdej sekcji technicznej.

Dokumentacja nie może zawierać:

```text
old container commands
obsolete image names
obsolete RBAC rules
obsolete test counts
obsolete service paths
obsolete authentication mechanisms
real secrets
real client tokens
private keys
```

Jeśli wdrożenie się zmienia, zaktualizuj dokumentację razem z implementacją.

---

# 172. Gotowość wydania

Pomyślna instalacja nie oznacza automatycznie, że LUMS ma oficjalne wydanie.

Obecny stan projektu celowo oddziela:

```text
Working implementation
Security audit
Documentation review
Release preparation
Versioning
Git tag
GitHub Release
```

Oficjalne wydanie LUMS powinno zostać utworzone dopiero po ukończeniu pełnej implementacji, przeglądu bezpieczeństwa, przeglądu dokumentacji i końcowej walidacji.

Do tego czasu traktuj repozytorium jako aktywnie rozwijany projekt.

---

# 173. Podstawa operacyjna

Obecnie udokumentowana podstawa to:

```text
LUMS Server
    Docker
    Nginx
    HTTPS
    SQLite
    RBAC
    CSRF
    Audit Logging
    Hardened Container

LUMS Agent
    Version 1.7.0

LUMS Watcher
    Version 1.2.1

Database
    journal_mode=wal
    busy_timeout=5000
    synchronous=2
    foreign_keys=ON (application connections)

Container
    non-root
    read-only root filesystem
    CapDrop=ALL
    no-new-privileges
    localhost-only application port

Roles
    Administrator
    Operator
    Viewer
```

Ta podstawa powinna być traktowana jako stan referencyjny dla rozwiązywania problemów i przyszłej konserwacji.

---

# 174. Instalacja kompletna

Instalacja jest kompletna, gdy:

```text
Server
  │
  ├── HTTPS works
  ├── Authentication works
  ├── RBAC works
  ├── Database is healthy
  ├── Container is hardened
  └── Persistent storage is verified
       │
       ▼
Client
  │
  ├── Agent reports
  ├── Watcher executes
  ├── Package manager works
  ├── Jobs complete
  ├── Results are validated
  └── Recovery works
       │
       ▼
Operations
  │
  ├── Backup exists
  ├── Restore is understood
  ├── Troubleshooting documentation is available
  └── Security baseline is maintained
```

Podstawowa zasada operacyjna LUMS to:

```text
Observe first.
Change second.
Verify third.
Document last.
```

Dla zmian produkcyjnych rozszerz to do:

```text
Backup
   ↓
Change
   ↓
Verify
   ↓
Document
```

Instalacja LUMS powinna zawsze pozostać powtarzalna, audytowalna i odtwarzalna.
