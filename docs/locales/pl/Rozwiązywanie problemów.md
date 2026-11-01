# LUMS — Rozwiązywanie problemów

Ten przewodnik zawiera procedury rozwiązywania problemów dla serwera LUMS, agentów Linux, watchera wykonania, zadań aktualizacji, uwierzytelniania, zarządzania pakietami, bazy danych i wdrożenia Docker.

Proces rozwiązywania problemów powinien zawsze rozpoczynać się od **obserwacji przed modyfikacją**.

Celem jest zidentyfikowanie pierwszego komponentu, w którym oczekiwane zachowanie ustaje, bez niepotrzebnej zmiany konfiguracji, stanu bazy danych, poświadczeń lub mechanizmów bezpieczeństwa.

---

## Pierwsze kroki: bezpieczne rozwiązywanie problemów

Jeśli dopiero zaczynasz przygodę z Linuksem, błąd nie oznacza automatycznie utraty danych. Nie zmieniaj kilku rzeczy naraz. Zacznij od poniższych kontroli i zanotuj, **kiedy** problem występuje i **jaka akcja** miała miejsce bezpośrednio przed nim.

### Pierwsze kontrole na serwerze LUMS

```bash
sudo docker ps -a --filter name=lums
sudo docker logs --tail 100 lums
sudo systemctl status nginx --no-pager
sudo nginx -t
```

`docker ps -a` pokazuje również zatrzymane kontenery. `docker logs` odczytuje ostatnie komunikaty aplikacji. `systemctl status` pokazuje, czy Nginx działa; `nginx -t` sprawdza jego konfigurację bez zmiany. Jeśli `nginx -t` zakończy się niepowodzeniem, **nie** przeładowuj Nginx, dopóki przyczyna nie zostanie usunięta.

### Pierwsze kontrole na zarządzanym kliencie

```bash
sudo systemctl status lums-agent.service --no-pager
sudo journalctl -u lums-agent.service -n 100 --no-pager
sudo systemctl status lums-agent-watcher.service --no-pager
sudo journalctl -u lums-agent-watcher.service -n 100 --no-pager
```

Agent i Watcher to oddzielne usługi: pomyślny raport Agenta nie dowodzi, że Watcher może uruchamiać zadania aktualizacji. Dla usługi `oneshot` stan `inactive` może być normalny po pomyślnym uruchomieniu; sprawdź również wynik i komunikaty logu.

### Przed udostępnieniem danych wyjściowych poleceń

Sprawdź logi i konfigurację pod kątem haseł, tokenów klientów, kluczy sesji lub API, kluczy prywatnych i danych osobowych. Nigdy nie udostępniaj zawartości plików sekretów ani pełnych wartości zmiennych środowiskowych. Jeśli potrzebujesz pomocy, udostępnij tylko odpowiednie komunikaty błędów po usunięciu wrażliwych informacji.

**Nie zaczynaj od** usuwania bazy danych lub wolumenu Docker, uruchamiania kontenera jako uprzywilejowany, wyłączania opcji bezpieczeństwa, usuwania plików blokad menedżera pakietów ani rotacji tokenów. Te działania mogą uszkodzić dane, zatrzeć dowody lub pogorszyć problem. Jeśli kontrola zakończy się niepowodzeniem, zapisz jej dane wyjściowe i przejdź do odpowiedniej sekcji poniżej.

---

# 1. Filozofia rozwiązywania problemów

LUMS składa się z kilku niezależnych komponentów.

Pomyślny raport klienta nie oznacza automatycznie, że wykonywanie aktualizacji działa.

Główna ścieżka operacyjna to:

```text
Linux Client
    │
    ├── LUMS Agent
    │
    └── Execution Watcher
            │
            ▼
          HTTPS
            │
            ▼
        Nginx
            │
            ▼
        LUMS API
            │
            ▼
         SQLite
```

Wykonywanie aktualizacji dodaje warstwę zarządzania pakietami:

```text
Browser
   │
   ▼
LUMS API
   │
   ▼
SQLite
   │
   ▼
Update Job
   │
   ▼
Execution Watcher
   │
   ▼
LUMS Agent
   │
   ▼
APT / pacman
   │
   ▼
Result
   │
   ▼
LUMS API
   │
   ▼
SQLite
```

Podczas rozwiązywania problemów zidentyfikuj **pierwszy zawodzący komponent**.

Na przykład:

```text
Agent report fails
    ↓
Check agent service
    ↓
Check network
    ↓
Check TLS
    ↓
Check client token
    ↓
Check LUMS API
```

Nie należy natychmiast:

* modyfikować bazy danych
* usuwać wolumenu Docker
* reinstalować Agenta
* rotować poświadczeń
* usuwać plików blokad menedżera pakietów
* wyłączać mechanizmów bezpieczeństwa
* czynić kontenera uprzywilejowanym

Te działania mogą zniszczyć użyteczne informacje diagnostyczne lub stworzyć dodatkowe problemy.

---

# 2. Podstawa diagnostyczna

Przed zbadaniem konkretnego problemu ustal bieżący stan głównych komponentów.

Produkcyjne wdrożenie LUMS używa:

```text
Application port: 127.0.0.1:5050
External access: HTTPS through Nginx
Database: /var/lib/lums/lums.db
Docker volume: lums-data
Agent: 1.7.0
Watcher: 1.2.1
```

Kontener produkcyjny jest utwardzony za pomocą:

```text
Read-only root filesystem
No Linux capabilities
no-new-privileges
Non-root application user
Protected secret mount
Dedicated persistent data volume
```

Port aplikacji jest celowo powiązany tylko z lokalnym hostem.

Oczekiwana ścieżka sieciowa to:

```text
Client / Browser
       │
       ▼
     HTTPS
       │
       ▼
    Nginx :443
       │
       ▼
127.0.0.1:5050
       │
       ▼
 Docker container
       │
       ▼
    LUMS :5000
```

---

# 3. Pierwsze kontrole diagnostyczne

## 3.1 Sprawdź kontener LUMS

Na serwerze LUMS:

```bash
sudo docker ps
```

Kontener `lums` powinien działać.

Aby uzyskać pełny przegląd kontenerów:

```bash
sudo docker ps -a \
    --filter name=lums
```

Nie usuwaj zatrzymanych kontenerów przed ich zbadaniem.

Starsze kontenery awaryjne mogą zawierać użyteczne informacje podczas badania problemu z wdrożeniem.

---

## 3.2 Sprawdź ostatnie logi aplikacji

Sprawdź najnowsze logi LUMS:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Aby uzyskać dane na żywo:

```bash
sudo docker logs \
    -f \
    lums
```

Podczas badania konkretnego żądania lub zadania, w miarę możliwości rozpocznij przeglądanie logów przed odtworzeniem problemu.

Ułatwia to skorelowanie działania klienta z odpowiednim zdarzeniem po stronie serwera.

---

## 3.3 Sprawdź Nginx

Sprawdź reverse proxy:

```bash
sudo systemctl status nginx \
    --no-pager
```

Zweryfikuj konfigurację:

```bash
sudo nginx -t
```

Pomyślny test konfiguracji powinien zgłosić:

```text
syntax is ok
test is successful
```

Jeśli Nginx nie działa, dostęp HTTPS do LUMS zwykle zakończy się niepowodzeniem, nawet gdy kontener Docker jest zdrowy.

---

## 3.4 Sprawdź Agenta

Na zarządzanym kliencie Linux:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Sprawdź ostatnie dane wyjściowe Agenta:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Dla usługi `Type=oneshot` stan nieaktywny po pomyślnym wykonaniu może być normalny.

Ważna jest informacja o wyniku wykonania.

Pomyślne wykonanie powinno zakończyć się:

```text
status=0/SUCCESS
```

---

## 3.5 Sprawdź Execution Watcher

Watcher jest oddzielnym komponentem od Agenta raportującego.

Sprawdź go niezależnie:

```bash
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Sprawdź ostatnie dane wyjściowe:

```bash
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 100 \
    --no-pager
```

Pomyślny raport Agenta **nie** dowodzi więc, że watcher wykonania działa poprawnie.

---

## 3.6 Sprawdź timery LUMS

Sprawdź wszystkie odpowiednie timery:

```bash
sudo systemctl list-timers \
    --all | grep lums
```

Oczekiwane timery obejmują mechanizmy planowania Agenta i watchera.

Jeśli timer jest brakujący lub nieaktywny, sprawdź odpowiednią jednostkę przed zmianą czegokolwiek.

---

# 4. Kontener LUMS nie działa

Jeśli kontener `lums` nie działa, nie odtwarzaj go natychmiast.

Najpierw sprawdź jego stan:

```bash
sudo docker ps -a \
    --filter name=lums
```

Następnie sprawdź kontener:

```bash
sudo docker inspect lums
```

Sprawdź ostatnie logi:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Sprawdź stan wyjścia:

```bash
sudo docker inspect \
    --format '{{.State.Status}} {{.State.ExitCode}}' \
    lums
```

Wynik może pomóc rozróżnić:

```text
Normal shutdown
Application failure
Configuration failure
Container runtime failure
Health/startup problem
```

Jeśli kontener zakończył się nieoczekiwanie, zachowaj logi i stan kontenera przed jego zastąpieniem.

---

# 5. Kontener uruchamia się, ale LUMS jest nieosiągalny

Aplikacja LUMS nie jest przeznaczona do bezpośredniego dostępu przez port aplikacji Docker z sieci.

Aplikacja produkcyjna jest powiązana z:

```text
127.0.0.1:5050
```

Zweryfikuj powiązanie portu:

```bash
sudo docker port lums
```

Sprawdź również nasłuchy hosta:

```bash
sudo ss -lntp | grep -E ':443|:5050'
```

Oczekiwana architektura to:

```text
HTTPS :443
    │
    ▼
  Nginx
    │
    ▼
127.0.0.1:5050
    │
    ▼
Docker
    │
    ▼
LUMS :5000
```

Jeśli kontener działa, ale HTTPS zawodzi, zbadaj warstwy indywidualnie:

1. Kontener Docker
2. Lokalny port aplikacji
3. Konfiguracja Nginx
4. TLS
5. Ścieżka firewalla/sieci

Nie wystawiaj portu `5050` publicznie jako skrótu do rozwiązywania problemów.

---

# 6. Nginx zwraca błąd

Sprawdź usługę:

```bash
sudo systemctl status nginx \
    --no-pager
```

Zweryfikuj konfigurację:

```bash
sudo nginx -t
```

Sprawdź ostatnie komunikaty Nginx:

```bash
sudo journalctl \
    -u nginx \
    -n 100 \
    --no-pager
```

Następnie sprawdź, czy kontener LUMS faktycznie działa:

```bash
sudo docker ps
```

Błąd reverse proxy nie oznacza automatycznie, że sama aplikacja LUMS jest uszkodzona.

Możliwe miejsca awarii obejmują:

```text
Browser
   ↓
TLS
   ↓
Nginx
   ↓
127.0.0.1:5050
   ↓
Docker
   ↓
LUMS
```

Testuj warstwy osobno, zamiast zmieniać kilka komponentów naraz.

---

# 7. Problemy z HTTPS / TLS

Najpierw przetestuj endpoint HTTPS:

```bash
curl -I https://LUMS-SERVER/
```

Jeśli weryfikacja certyfikatu nie powiedzie się, ustal, czy problem dotyczy:

```text
Certificate
Certificate chain
Hostname
Trust store
Nginx configuration
Client CA configuration
```

Zweryfikuj Nginx:

```bash
sudo nginx -t
```

Jeśli certyfikat lub konfiguracja TLS zostały celowo zmienione, przeładuj Nginx:

```bash
sudo systemctl reload nginx
```

Następnie przetestuj ponownie:

```bash
curl -I https://LUMS-SERVER/
```

Klienci używający prywatnego urzędu certyfikacji muszą zaufać odpowiedniemu certyfikatowi CA.

Nie wyłączaj weryfikacji certyfikatu TLS jako stałego obejścia.

Pomyślny test łączności, który pomija walidację certyfikatu, nie dowodzi, że produkcyjna konfiguracja TLS jest poprawna.

---

# 8. Usługa Agenta zawodzi

Sprawdź usługę:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Przeczytaj ostatni journal:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Uruchom usługę ponownie dopiero po sprawdzeniu poprzedniego wyniku:

```bash
sudo systemctl start \
    lums-agent.service
```

Następnie sprawdź:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

oraz:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Szukaj:

```text
Configuration errors
Missing environment values
TLS errors
Authentication failures
API errors
Python exceptions
Package-manager errors
```

Nie reinstaluj Agenta tylko dlatego, że jedno wykonanie zakończyło się niepowodzeniem.

---

# 9. Agent zgłasza brak `LUMS_TOKEN`

Agent zwykle otrzymuje konfigurację produkcyjną przez środowisko usługi systemd.

Jeśli Agent jest uruchamiany ręcznie z powłoki, `EnvironmentFile` systemd nie jest automatycznie ładowany do tej powłoki.

Dlatego:

```bash
sudo /opt/lums-agent/agent.py --version
```

może zachowywać się inaczej niż:

```bash
sudo systemctl start \
    lums-agent.service
```

gdy token jest dostarczany wyłącznie przez konfigurację systemd.

Podczas badania problemów z uwierzytelnianiem najpierw przetestuj rzeczywistą usługę:

```bash
sudo systemctl start \
    lums-agent.service
```

Następnie sprawdź:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Nie kopiuj produkcyjnych tokenów do poleceń powłoki bez potrzeby.

Nigdy nie wypisuj produkcyjnego tokena do logu diagnostycznego.

---

# 10. Agent nie może połączyć się z serwerem

Zacznij od łączności sieciowej:

```bash
ping LUMS-SERVER
```

Następnie przetestuj HTTPS:

```bash
curl -I https://LUMS-SERVER/
```

Jeśli HTTPS działa, ale Agent nadal zawodzi, zbadaj:

```text
Client configuration
Client token
TLS trust
API response
Client identity
Agent version
```

Sprawdź Agenta:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Jednocześnie sprawdź serwer:

```bash
sudo docker logs \
    --tail 200 \
    lums
```

Pomaga to ustalić, czy żądanie w ogóle dociera do LUMS.

Jeśli klient widzi błąd połączenia, a serwer nie pokazuje odpowiedniego żądania, zbadaj ścieżkę sieciową lub TLS przed zmianą konfiguracji aplikacji.

---

# 11. Kontynuuj rozwiązywanie problemów

Jeśli podstawowe warstwy serwera, Docker, Nginx, TLS i Agenta działają, kontynuuj z:

```text
Client Authentication
Token Rotation
Update Detection
Execution Watcher
Idle Detection
Pending Jobs
```

Następna sekcja kontynuuje temat uwierzytelniania klientów i problemów związanych z tokenami.

# 12. Uwierzytelnianie klientów

LUMS używa uwierzytelniania specyficznego dla klienta do komunikacji Agenta.

Po zarejestrowaniu klient otrzymuje poświadczenia używane do uwierzytelnionej komunikacji z serwerem LUMS.

Błędy uwierzytelniania należy badać bez ujawniania tokena klienta.

---

## 12.1 Klient nie jest akceptowany przez LUMS

Jeśli Agent zgłasza błąd uwierzytelniania, najpierw sprawdź log Agenta:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Następnie sprawdź logi kontenera LUMS:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Szukaj:

```text
401 Unauthorized
403 Forbidden
Invalid client token
Unknown client
Authentication failure
```

Odpowiedź `401` generalnie wskazuje na problem z uwierzytelnianiem.

Odpowiedź `403` może wskazywać, że uwierzytelnianie powiodło się, ale żądana operacja nie jest dozwolona.

Nie rotuj tokena natychmiast.

Najpierw ustal, czy problem to:

```text
Wrong token
Wrong client ID
Disabled client
Incorrect server URL
TLS problem
Malformed request
Server-side authentication failure
```

---

## 12.2 Klient istnieje, ale uwierzytelnianie zawodzi

Sprawdź, czy klient nadal istnieje w interfejsie administracyjnym LUMS.

Nie modyfikuj rekordu klienta tylko dlatego, że żądanie Agenta zakończyło się niepowodzeniem.

Jeśli klient istnieje, porównaj skonfigurowaną tożsamość klienta z tożsamością używaną przez Agenta.

Sam produkcyjny token nigdy nie może być wypisywany w danych wyjściowych diagnostycznych.

Do rozwiązywania problemów używaj metadanych konfiguracji i statusu usługi, zamiast ujawniać poświadczenia.

---

# 13. Rotacja tokenów klientów

Rotacja tokenów klientów unieważnia poprzedni token i zastępuje go nowym poświadczeniem.

Jeśli token został celowo zrotowany, dotknięty Agent musi otrzymać nowy token, zanim będzie mógł ponownie się uwierzytelnić.

Oczekiwana sekwencja to:

```text
Administrator
    │
    ▼
Rotate client token
    │
    ▼
Old token becomes invalid
    │
    ▼
New token assigned to client
    │
    ▼
Agent configuration updated
    │
    ▼
Agent reports again
```

Jeśli Agent nadal używa starego tokena, uwierzytelnianie zakończy się niepowodzeniem.

---

## 13.1 Po rotacji tokena

Sprawdź usługę Agenta:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Następnie uruchom Agenta przez systemd:

```bash
sudo systemctl start \
    lums-agent.service
```

Sprawdź wynik:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Jeśli uwierzytelnianie nadal zawodzi, sprawdź logi serwera:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Nie rotuj tokena wielokrotnie.

Powtarzająca się rotacja może utrudnić ustalenie, które poświadczenie jest obecnie wdrożone na kliencie.

---

# 14. Klient jest wyłączony

Wyłączonego klienta nie należy traktować jako aktywnego zarządzanego klienta.

Jeśli Agent należący do wyłączonego klienta próbuje komunikować się, sprawdź wynik uwierzytelniania po stronie serwera.

Sprawdź:

```text
Client identity
Client enabled state
Authentication result
Agent configuration
```

Nie włączaj klienta ponownie tylko po to, by błąd zniknął.

Najpierw ustal, dlaczego klient został wyłączony.

---

# 15. Wykrywanie aktualizacji

Wykrywanie aktualizacji składa się z kilku niezależnych kroków.

Agent musi:

1. wykonać zapytanie menedżera pakietów
2. przetworzyć wynik
3. wysłać wynik do LUMS
4. LUMS musi zweryfikować wynik
5. LUMS musi utrwalić wynik
6. interfejs użytkownika musi wyświetlić bieżący stan

Awaria w którymkolwiek kroku może sprawić, że informacje o aktualizacjach będą wyglądać niepoprawnie.

Podstawowy przepływ to:

```text
APT / pacman
     │
     ▼
Agent
     │
     ▼
HTTPS
     │
     ▼
LUMS API
     │
     ▼
SQLite
     │
     ▼
Web UI
```

---

## 15.1 Brak wyświetlanych aktualizacji

Najpierw ustal, czy klient faktycznie zaraportował pomyślnie.

Sprawdź:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 100 \
    --no-pager
```

Następnie sprawdź serwer:

```bash
sudo docker logs \
    --tail 100 \
    lums
```

Jeśli Agent zakończył się pomyślnie, ale nie są wyświetlane żadne aktualizacje, zbadaj stan API i bazy danych przed zmianą menedżera pakietów.

---

## 15.2 Wykrywanie aktualizacji Debian / Ubuntu

Menedżer pakietów Debian używa APT.

Podczas badania problemów związanych z APT najpierw sprawdź, czy sam APT działa:

```bash
sudo apt update
```

Nie uruchamiaj automatycznie aktualizacji pakietów podczas rozwiązywania problemów.

Celem tego testu jest ustalenie, czy metadane repozytorium mogą zostać pomyślnie odświeżone.

Jeśli APT zgłasza błędy repozytorium, DNS, TLS, podpisu lub blokady, rozwiąż podstawowy problem APT przed zbadaniem LUMS.

---

## 15.3 Wykrywanie aktualizacji Arch Linux

Arch Linux używa `pacman`.

Sprawdź metadane repozytorium:

```bash
sudo pacman -Sy
```

Używaj tego tylko wtedy, gdy odświeżenie metadanych repozytorium jest rzeczywiście wymagane do diagnostyki.

Nie łącz niepotrzebnej aktualizacji systemu z testem diagnostycznym.

W przypadku błędów związanych z pakietami sprawdź dokładne dane wyjściowe `pacman` przed zmianą konfiguracji.

---

# 16. Dostępne aktualizacje różnią się między LUMS a klientem

Informacje o aktualizacjach mogą się zmieniać między dwiema obserwacjami.

Na przykład:

```text
Client reports updates
        ↓
Repository metadata changes
        ↓
Package is upgraded manually
        ↓
LUMS displays older information
```

Dlatego zawsze bierz pod uwagę znacznik czasu ostatniego pomyślnego raportu klienta.

Różnica nie oznacza automatycznie problemu z bazą danych.

Sprawdź:

```text
Last Agent execution
Last successful report
Package-manager state
Repository metadata
Displayed update state
```

---

# 17. Zarządzanie pakietami

Zarządzanie pakietami LUMS jest oddzielone od filtra zainstalowanych pakietów wyświetlanego na stronie klienta.

Przepływ zarządzania pakietami to:

```text
User
 │
 ▼
Package Search
 │
 ▼
LUMS API
 │
 ▼
Agent
 │
 ▼
APT / pacman
 │
 ▼
Search Result
 │
 ▼
LUMS API
 │
 ▼
Web UI
```

Instalowanie, usuwanie lub aktualizowanie pakietu korzysta z normalnego mechanizmu zadań LUMS.

Oczekiwana ścieżka wykonania to:

```text
Package Action
     │
     ▼
Update Job
     │
     ▼
Execution Watcher
     │
     ▼
Agent
     │
     ▼
APT / pacman
```

---

## 17.1 Wyszukiwanie pakietów nie zwraca wyników

Najpierw sprawdź, czy Agent działa:

```bash
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Następnie sprawdź journal Agenta:

```bash
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Dla klientów opartych na Debianie sprawdź metadane APT.

Dla klientów opartych na Arch sprawdź metadane repozytorium pacman.

Nie zakładaj, że pusty wynik wyszukiwania oznacza, że baza danych LUMS jest pusta.

Wyszukiwanie jest wykonywane przez menedżera pakietów klienta.

---

## 17.2 Wyszukiwanie pakietów działa, ale instalacja zawodzi

Pomyślne wyszukiwanie dowodzi tylko, że menedżer pakietów mógł zlokalizować pakiet.

Nie dowodzi, że instalacja się powiedzie.

Możliwe przyczyny obejmują:

```text
Dependency conflicts
Repository changes
Package no longer available
Insufficient privileges
Package-manager lock
Disk-space problems
Network problems
Package-manager errors
```

Sprawdź odpowiednie zadanie aktualizacji.

Journal Agenta powinien zawierać wynik menedżera pakietów.

---

# 18. Zadania instalacji pakietów

Instalacja pakietów korzysta z normalnej infrastruktury zadań aktualizacji.

Odpowiednie działanie to:

```text
INSTALL_PACKAGE
```

Podczas rozwiązywania problemów z instalacją:

1. Sprawdź stan zadania w LUMS.
2. Sprawdź wykonanie Agenta.
3. Sprawdź dane wyjściowe menedżera pakietów.
4. Sprawdź końcowy wynik zaraportowany do LUMS.

Nie modyfikuj ręcznie statusu zadania w SQLite.

Oczekiwany cykl życia to:

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

Nieudana instalacja pakietu powinna pozostać identyfikowalna przez normalne mechanizmy zadań i audytu.

---

# 19. Zadania usuwania pakietów

Usuwanie pakietów podlega temu samemu cyklowi życia zadania.

Działanie to:

```text
REMOVE_PACKAGE
```

Gdy usunięcie zawiedzie, sprawdź:

```text
Update job
Agent journal
Package-manager output
Final job result
```

Nie usuwaj ręcznie rekordów bazy danych, aby ukryć nieudaną operację na pakiecie.

Nieudane zadanie jest użyteczną informacją diagnostyczną.

---

# 20. Zadania aktualizacji pakietów

Aktualizacja konkretnego pakietu używa:

```text
UPDATE_PACKAGE
```

Pakiet musi być znany LUMS jako mający dostępną aktualizację, zanim zadanie zostanie utworzone.

Jeśli interfejs użytkownika nie oferuje oczekiwanej aktualizacji pakietu:

1. odśwież informacje o aktualizacjach
2. sprawdź stan menedżera pakietów
3. sprawdź wynik dostępnych aktualizacji
4. sprawdź logi serwera, jeśli stan jest niespójny

Nie wstawiaj ręcznie rekordów aktualizacji do SQLite.

---

# 21. Zadania aktualizacji systemu

Pełna aktualizacja systemu używa:

```text
UPDATE_SYSTEM
```

Różni się to od:

```text
UPDATE_PACKAGE
```

Aktualizacja systemu może wpływać na wiele pakietów i może wymagać ponownego uruchomienia w zależności od systemu operacyjnego i wynikowego stanu pakietów.

Podczas rozwiązywania problemów z aktualizacją systemu ustal, czy awaria wystąpiła podczas:

```text
Update preparation
Package-manager execution
Result collection
Reboot detection
Post-reboot reporting
```

---

# 22. Blokady menedżera pakietów

Menedżery pakietów mogą odmówić operacji, gdy inny proces zarządzania pakietami jest już uruchomiony.

Typowe przykłady obejmują:

```text
APT is already running
dpkg is locked
pacman is locked
```

Najpierw zidentyfikuj proces trzymający blokadę.

Nie usuwaj bezrefleksyjnie plików blokad.

Plik blokady może wskazywać, że inny proces zarządzania pakietami jest legalnie aktywny.

Usunięcie go podczas uruchomionej operacji na pakiecie może uszkodzić stan zarządzania pakietami.

Prawidłowa sekwencja rozwiązywania problemów to:

```text
Lock error
   ↓
Identify active process
   ↓
Determine whether it is legitimate
   ↓
Wait or resolve the process safely
   ↓
Retry operation
```

---

# 23. Awaria menedżera pakietów vs. awaria LUMS

Zawsze rozróżniaj awarię menedżera pakietów od awarii LUMS.

Na przykład:

```text
APT fails
    ↓
Agent reports APT failure
    ↓
LUMS stores FAILED result
```

W tym przypadku LUMS może działać poprawnie, mimo że zadanie zakończyło się niepowodzeniem.

Odwrotnie:

```text
APT succeeds
    ↓
Agent cannot report result
    ↓
LUMS never receives SUCCESS
```

Tutaj operacja na pakiecie mogła się powieść, podczas gdy ścieżka raportowania LUMS zawiodła.

Dlatego wynik menedżera pakietów i wynik zadania LUMS należy badać osobno.

---

# 24. Użyteczne rozdzielenie diagnostyczne

Gdy zadanie pakietu zawiedzie, najpierw sklasyfikuj awarię:

```text
A. Package-manager failure
B. Agent execution failure
C. Agent reporting failure
D. Server/API failure
E. Database persistence failure
F. UI display problem
```

Ta klasyfikacja zapobiega modyfikowaniu niepowiązanych komponentów.

Błąd menedżera pakietów nie powinien automatycznie skutkować przebudową Docker.

Problem z wyświetlaniem w interfejsie użytkownika nie powinien automatycznie skutkować usunięciem bazy danych.

Błąd uwierzytelniania nie powinien automatycznie skutkować reinstalacją Agenta.

---

# 25. Następny obszar rozwiązywania problemów

Jeśli uwierzytelnianie klientów, wykrywanie aktualizacji i zarządzanie pakietami działają, następnym obszarem diagnostycznym jest sam cykl życia wykonania:

```text
Update Job
    ↓
Watcher
    ↓
Agent
    ↓
Execution
    ↓
Result
    ↓
Checkpoint / Recovery
    ↓
Final Job State
```

Następna sekcja obejmuje **Execution Watcher, wykrywanie bezczynności, stan zadań, odzyskiwanie i obsługę ponownego uruchomienia**.

# 26. Wykonywanie zadań aktualizacji

Zadania aktualizacji LUMS są wykonywane asynchronicznie przez Agenta i Execution Watcher.

Normalna ścieżka wykonania to:

```text
User
 │
 ▼
LUMS API
 │
 ▼
SQLite
 │
 ▼
Pending Job
 │
 ▼
Execution Watcher
 │
 ▼
Agent
 │
 ▼
Package Manager
 │
 ▼
Result
 │
 ▼
LUMS API
 │
 ▼
SQLite
```

Zadanie widoczne w interfejsie użytkownika niekoniecznie jest już wykonywane.

Zawsze najpierw ustal bieżący stan zadania.

---

## 26.1 Zadanie utknęło w stanie `PENDING`

Jeśli zadanie pozostaje w stanie `PENDING`, sprawdź Execution Watcher przed zbadaniem Agenta.

Sprawdź watcher:

```bash id="wq5h3v"
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Sprawdź ostatnie dane wyjściowe watchera:

```bash id="8y0v7e"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Następnie sprawdź Agenta:

```bash id="j8x4qm"
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Oczekujące zadanie zwykle wskazuje, że etap wykonania jeszcze się nie rozpoczął.

Możliwe przyczyny obejmują:

```text
Watcher is not running
Watcher timer is not running
Client is offline
Client is not idle
Client has not reported recently
Job is not eligible for execution yet
```

Nie zmieniaj ręcznie stanu zadania w SQLite.

---

# 27. Zadanie utknęło w stanie `RUNNING`

Zadanie `RUNNING` wskazuje, że wykonanie się rozpoczęło.

Najpierw ustal, czy Agent faktycznie wykonuje zadanie.

Sprawdź:

```bash id="s2z5ek"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Następnie sprawdź watcher:

```bash id="x4f6cb"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Uruchomione zadanie może zająć trochę czasu w zależności od:

```text
Package count
Repository speed
Network latency
Package-manager operations
System load
Reboot requirements
```

Nie przerywaj aktywnej operacji na pakiecie tylko dlatego, że interfejs użytkownika jeszcze się nie zaktualizował.

Najpierw ustal, czy podstawowy proces jest nadal aktywny.

---

# 28. Zadanie ma stan `FAILED`

Nieudane zadanie niekoniecznie wskazuje na awarię serwera LUMS.

Ustal, która warstwa spowodowała awarię.

Sprawdź:

```text id="5t9b83"
Job state
Agent execution result
Package-manager result
Server logs
Agent logs
```

Główne kategorie to:

```text
Package-manager failure
Agent execution failure
Agent reporting failure
Server/API failure
Authentication failure
Recovery failure
```

Oryginalny błąd powinien być w miarę możliwości zachowany.

Nie zastępuj nieudanego zadania ręcznie utworzonym rekordem sukcesu.

---

# 29. Zadanie ma stan `SUCCESS`, ale pakiet nie został zmieniony

Pomyślne zadanie LUMS oznacza, że żądana operacja zakończyła się zgodnie z wynikiem Agenta.

Jeśli oczekiwany stan pakietu nie odpowiada wynikowi zadania, zweryfikuj klienta bezpośrednio.

Dla systemów opartych na Debianie:

```bash id="gqdbm7"
dpkg-query -W \
    -f='${Package} ${Version}\n' \
    PACKAGE_NAME
```

Dla Arch Linux:

```bash id="2x9f7v"
pacman -Q \
    PACKAGE_NAME
```

Zastąp `PACKAGE_NAME` badanym pakietem.

Następnie porównaj lokalny stan pakietu z wynikiem LUMS.

Możliwe wyjaśnienia obejmują:

```text
Package was changed after the job
Package name refers to a virtual/provided package
Package-manager output was interpreted differently than expected
The job result was generated before another local change
```

Nie modyfikuj bazy danych LUMS, dopóki rozbieżność nie zostanie zidentyfikowana.

---

# 30. Execution Watcher

Execution Watcher jest odpowiedzialny za odkrywanie zadań kwalifikujących się do wykonania.

Watcher należy traktować jako niezależny komponent.

Sprawdź jego usługę:

```bash id="w5m0c8"
sudo systemctl status \
    lums-agent-watcher.service \
    --no-pager
```

Sprawdź jego timer:

```bash id="3v1x7r"
sudo systemctl list-timers \
    --all | grep lums
```

Sprawdź jego journal:

```bash id="d5m0xk"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Jeśli Agent działa, ale zadania nigdy się nie rozpoczynają, watcher powinien być jednym z pierwszych badanych komponentów.

---

# 31. Watcher działa, ale nie wykonuje zadań

Wykonanie watchera nie oznacza automatycznie, że zadanie zostanie uruchomione.

Zadanie musi spełniać warunki wykonania.

Sprawdź:

```text id="m7p2zq"
Client exists
Client is enabled
Client is reachable
Client has recent status
Client is eligible
Job is pending
Job is not already completed
Execution conditions are satisfied
```

Jeśli klient nie kwalifikuje się, watcher może poprawnie pozostawić zadanie w stanie oczekującym.

To niekoniecznie jest błąd.

---

# 32. Wykrywanie bezczynności

LUMS może używać informacji o bezczynności klienta przy podejmowaniu decyzji, czy zadanie powinno zostać wykonane.

Celem jest uniknięcie rozpoczynania operacji konserwacyjnych, gdy klient jest aktywnie używany.

Decyzję o bezczynności należy więc traktować jako warunek planowania, a nie jako awarię wykonania.

Klient może raportować pomyślnie, będąc jednocześnie uznanym za niebezczynnego.

Sekwencja rozwiązywania problemów to:

```text
Agent reports
     ↓
Idle information available?
     ↓
Idle state acceptable?
     ↓
Job eligible?
     ↓
Watcher executes
```

---

## 32.1 Klient raportuje, ale nie jest uznawany za bezczynnego

Sprawdź journal Agenta:

```bash id="5r2q1k"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Szukaj zaraportowanych informacji o bezczynności.

Następnie sprawdź watcher:

```bash id="2a6v8m"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Ważne rozróżnienie to:

```text
Agent communication successful
```

versus:

```text
Client eligible for maintenance execution
```

To są oddzielne stany.

---

# 33. Wykrywanie bezczynności jest niedostępne

Niektóre systemy mogą nie dostarczać wszystkich informacji o stanie bezczynności.

Niedostępny mechanizm bezczynności nie powinien być automatycznie interpretowany jako uszkodzony Agent.

Najpierw ustal zaraportowaną możliwość.

Odpowiednie pojęcia to:

```text
Idle supported
Idle source
Idle state
Idle duration
```

Jeśli platforma nie może dostarczyć oczekiwanych informacji o bezczynności, zbadaj implementację Agenta specyficzną dla platformy, zamiast modyfikować bazę danych serwera.

---

# 34. Odzyskiwanie zadań aktualizacji

LUMS używa punktów kontrolnych i odzyskiwania, aby zapobiec traktowaniu przerwanych zadań aktualizacji jako zakończonych.

Zadanie może zostać przerwane z powodu:

```text
Agent restart
Client reboot
Network interruption
Package-manager interruption
Server restart
Watcher restart
System failure
```

Odzyskiwanie musi rozróżniać pracę już wykonaną od pracy, która jeszcze wymaga wykonania.

Zasada jest następująca:

```text
Ukończona praca pozostaje ukończona.
Niedokończona praca nadal może zostać odzyskana.
```

---

# 35. Przerwane zadanie

Jeśli zadanie zostało przerwane, najpierw sprawdź jego stan.

Następnie sprawdź Agenta:

```bash id="3u8d4k"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Sprawdź watcher:

```bash id="w4x1b9"
sudo journalctl \
    -u lums-agent-watcher.service \
    -n 200 \
    --no-pager
```

Nie oznaczaj ręcznie zadania jako pomyślnego.

Mechanizm odzyskiwania powinien określić, które elementy pakietów zostały już ukończone.

---

# 36. Odzyskiwanie powtarza operację na pakiecie

Gdy odzyskiwanie jest wyzwalane, już pomyślne elementy pakietów nie powinny być niepotrzebnie wykonywane ponownie.

Model odzyskiwania opiera się na stanie na poziomie elementów.

Koncepcyjnie:

```text
Job
 ├── Package A → SUCCESS
 ├── Package B → SUCCESS
 ├── Package C → FAILED
 └── Package D → PENDING
```

Odzyskiwanie powinno zachować pomyślne elementy i kontynuować pozostałą pracę.

Jeśli to zachowanie wydaje się nieprawidłowe, sprawdź historię zadania i elementów pakietów przed zmianą bazy danych.

---

# 37. Klient uruchamia się ponownie podczas aktualizacji

Ponowne uruchomienie może przerwać proces Agenta.

Oczekiwana ścieżka odzyskiwania to:

```text
Update starts
    ↓
Package operation
    ↓
Client reboot
    ↓
Agent starts again
    ↓
State is reported
    ↓
LUMS evaluates recovery
```

Ponowne uruchomienie nie oznacza więc automatycznie, że zadanie nie powiodło się trwale.

Sprawdź usługę Agenta po powrocie klienta:

```bash id="jjh3u8"
sudo systemctl status \
    lums-agent.service \
    --no-pager
```

Następnie sprawdź ostatnie wykonania:

```bash id="h7y5gk"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

---

# 38. Wykrywanie ponownego uruchomienia

Wykrywanie ponownego uruchomienia służy do ustalenia, czy system został ponownie uruchomiony w ramach operacji aktualizacji.

Jest to szczególnie istotne, gdy aktualizacja zmienia pakiety wymagające restartu lub ponownego uruchomienia.

Dla Arch Linux wykrywania ponownego uruchomienia nie wolno mylić ze statusem wyjścia menedżera pakietów.

Operacja na pakiecie może się powieść, podczas gdy system nadal wymaga ponownego uruchomienia.

Podczas rozwiązywania problemów z obsługą ponownego uruchomienia porównaj:

```text
Package operation result
Reboot requirement
Actual reboot state
Post-reboot Agent report
Final LUMS job state
```

---

# 39. Wynik zadania nie został zaraportowany

Jeśli operacja na pakiecie wydaje się zakończona, ale LUMS nie pokazuje końcowego wyniku, zbadaj ścieżkę raportowania.

Sprawdź Agenta:

```bash id="t0r8kf"
sudo journalctl \
    -u lums-agent.service \
    -n 200 \
    --no-pager
```

Następnie sprawdź serwer:

```bash id="h5n1xv"
sudo docker logs \
    --tail 200 \
    lums
```

Jeśli Agent zgłasza błąd, podczas gdy sama operacja na pakiecie zakończyła się sukcesem, sklasyfikuj problem jako awarię raportowania, a nie awarię zarządzania pakietami.

---

# 40. Ponowne uruchomienie serwera podczas wykonywania zadania

Ponownego uruchomienia serwera nie należy automatycznie traktować jako dowodu, że operacja aktualizacji nie powiodła się.

Stan zadania należy ocenić po ponownym udostępnieniu serwera.

Sprawdź:

```text id="j4t7yw"
Container state
Database availability
Job state
Client state
Agent report
Watcher state
```

Mechanizm odzyskiwania jest odpowiedzialny za ustalenie, czy przerwana praca może bezpiecznie kontynuować.

Nie przepisuj ręcznie stanów zadań po ponownym uruchomieniu serwera.

---

# 41. Baza danych jest dostępna, ale stan zadania wygląda nieprawidłowo

Jeśli SQLite jest dostępny, ale stan zadania wydaje się niespójny, sprawdź logi aplikacji i audytu przed modyfikacją bazy danych.

Przydatne informacje obejmują:

```text
Job ID
Client ID
Job action
Job creation time
Current state
Package-item states
Agent result
Recovery events
Audit events
```

Baza danych jest magazynem danych aplikacji, a nie interfejsem do ręcznej naprawy.

Bezpośrednie modyfikacje mogą ominąć walidację, autoryzację, audyt i logikę odzyskiwania.

---

# 42. Ręczne zmiany stanu zadania

Ręczne zmiany SQL stanu zadania aktualizacji nie powinny być używane jako normalne rozwiązywanie problemów.

Unikaj operacji takich jak:

```sql id="8hbyqv"
UPDATE update_jobs ...
```

lub:

```sql id="n1h7yr"
DELETE FROM update_jobs ...
```

chyba że kontrolowana procedura odzyskiwania bazy danych wyraźnie tego wymaga.

Jeśli naprawa na poziomie bazy danych jest naprawdę konieczna, zachowaj kopię zapasową i udokumentuj dokładną zmianę przed jej zastosowaniem.

Normalne problemy operacyjne powinny być rozwiązywane przez mechanizmy aplikacji i Agenta.

---

# 43. Macierz diagnostyczna Watcher i Agent

Użyj poniższej macierzy do zidentyfikowania najbardziej prawdopodobnej warstwy:

| Objaw                                              | Pierwszy komponent do sprawdzenia |
| -------------------------------------------------- | --------------------------------- |
| Klient nie może się uwierzytelnić                  | Agent + LUMS API                  |
| Klient raportuje pomyślnie, ale zadanie pozostaje oczekujące | Execution Watcher          |
| Zadanie przechodzi w stan running, ale się nie kończy | Agent + menedżer pakietów      |
| Operacja na pakiecie zawodzi                       | Menedżer pakietów                 |
| Operacja na pakiecie się powodzi, ale brak wyniku  | Raportowanie Agenta               |
| Klient uruchomił się ponownie podczas aktualizacji | Agent + odzyskiwanie              |
| Zadanie pozostaje niespójne po restarcie           | Odzyskiwanie + stan bazy danych   |
| Zadanie nigdy nie jest odkrywane                   | Watcher + timer                   |
| Klient nie kwalifikuje się                         | Bezczynność / stan klienta        |
| Interfejs użytkownika pokazuje nieaktualny stan    | API + ostatni raport klienta      |

Ta macierz jest punktem wyjścia, a nie substytutem sprawdzenia rzeczywistych logów i stanu zadania.

---

# 44. Następny obszar rozwiązywania problemów

Po zweryfikowaniu wykonywania zadań kolejne obszary to:

```text
SQLite and database state
RBAC and user management
Authentication sessions
Application and audit logging
Container security
Tests and CI
```

Te obszary należy badać oddzielnie od wykonywania pakietów.

# 45. Rozwiązywanie problemów z SQLite i bazą danych

LUMS używa SQLite jako bazy danych aplikacji.

Baza danych produkcyjna jest przechowywana w trwałym wolumenie Docker:

```text id="9c6w3e"
/var/lib/lums/lums.db
```

Baza danych jest zarządzana przez aplikację i normalnie nie może być modyfikowana ręcznie.

Podczas badania problemów związanych z bazą danych najpierw ustal, czy problem dotyczy:

```text id="4k4z1m"
Database availability
Database locking
Application configuration
Data consistency
Migration state
Application logic
```

---

# 46. Baza danych jest niedostępna

Jeśli LUMS zgłasza błąd bazy danych, najpierw sprawdź, czy kontener działa:

```bash id="0l5q6h"
sudo docker ps
```

Następnie sprawdź logi aplikacji:

```bash id="6j5p8m"
sudo docker logs \
    --tail 200 \
    lums
```

Nie usuwaj natychmiast wolumenu Docker.

Trwały wolumen zawiera produkcyjne dane aplikacji.

Jego usunięcie może trwale usunąć:

```text id="4bq9rj"
Users
Clients
Client configuration
Update jobs
Audit data
Application state
```

---

# 47. Blokowanie bazy danych SQLite

Problemy z blokowaniem SQLite należy badać przez logi aplikacji.

Sprawdź:

```bash id="l8f6vk"
sudo docker logs \
    --tail 200 \
    lums
```

Aplikacja produkcyjna używa:

```text id="2d3m8x"
journal_mode = wal
busy_timeout = 5000
synchronous = 2
```

Aplikacja włącza również egzekwowanie kluczy obcych SQLite dla swoich połączeń z bazą danych.

Blokada bazy danych nie oznacza automatycznie, że baza danych jest uszkodzona.

Możliwe przyczyny obejmują:

```text id="9w4qcz"
Concurrent writes
Long-running transaction
Application process still using the database
Unexpected process termination
Filesystem problem
```

Nie usuwaj ręcznie plików journal SQLite.

---

# 48. Klucze obce SQLite

LUMS jawnie włącza egzekwowanie kluczy obcych SQLite na poziomie aplikacji.

Oznacza to, że relacje między rekordami bazy danych są walidowane przez SQLite po ustanowieniu połączenia aplikacji.

Jeśli wystąpi błąd związany z kluczem obcym, najpierw sprawdź logi aplikacji.

Nie wyłączaj egzekwowania kluczy obcych, aby operacja zakończyła się sukcesem.

Awaria klucza obcego może wskazywać na problem z logiką aplikacji lub integralnością danych.

---

# 49. Integralność bazy danych SQLite

Jeśli istnieje podejrzenie uszkodzenia bazy danych, najpierw przestań dokonywać niepotrzebnych zmian.

Zachowaj bieżący stan i sprawdź logi aplikacji.

Kontrolowaną kontrolę integralności można przeprowadzić na kopii bazy danych.

Nie wykonuj destrukcyjnych operacji naprawczych bezpośrednio na produkcyjnej bazie danych, chyba że udokumentowana procedura odzyskiwania tego wymaga.

Ogólna zasada jest następująca:

```text id="t4d1km"
Preserve
   ↓
Inspect
   ↓
Verify
   ↓
Recover
   ↓
Validate
```

Nigdy nie zaczynaj od:

```text id="z1f6rw"
Delete database
Recreate database
Recreate Docker volume
```

---

# 50. Migracje bazy danych

LUMS używa migracji aplikacji do wprowadzania zmian w schemacie bazy danych.

Gdy wystąpi problem z migracją, sprawdź logi kontenera:

```bash id="x4h9vf"
sudo docker logs \
    --tail 200 \
    lums
```

Szukaj:

```text id="m2x7kc"
Migration failure
SQL error
Duplicate column
Missing table
Constraint error
Migration already applied
```

Nie edytuj ręcznie rekordów migracji, chyba że system migracji wymaga konkretnej kontrolowanej procedury odzyskiwania.

Migracja, która została już zastosowana, normalnie nie powinna być ponownie uruchamiana ręcznie.

---

# 51. Wolumen bazy danych

Baza danych LUMS jest przechowywana w trwałym wolumenie Docker:

```text id="p6m3jw"
lums-data
```

Sprawdź wolumen:

```bash id="v4c7yq"
sudo docker volume inspect \
    lums-data
```

Wolumen musi pozostać trwały podczas normalnego odtwarzania kontenera.

Sam kontener aplikacji jest jednorazowy.

Dane aplikacji nie są.

Dlatego:

```text id="z9f4ws"
Container
    ≠
Persistent database
```

Odtworzenia kontenera nie wolno mylić z odtworzeniem wolumenu danych.

---

# 52. Miejsce na dysku bazy danych

SQLite wymaga dostępnego miejsca w systemie plików do normalnego działania.

Sprawdź system plików hosta:

```bash id="j6k1pt"
df -h
```

Sprawdź również dostępność i-węzłów:

```bash id="q2c5ra"
df -i
```

Niski poziom miejsca na dysku może powodować błędy bazy danych, które początkowo wyglądają jak problemy z aplikacją.

Jeśli baza danych nagle staje się tylko do odczytu lub zapisy zaczynają zawodzić, sprawdź pojemność systemu plików przed modyfikacją konfiguracji SQLite.

---

# 53. Rozwiązywanie problemów z RBAC

LUMS używa kontroli dostępu opartej na rolach.

Obecne role to:

```text id="k8w5j2"
Administrator
Operator
Viewer
```

Uprawnienia są celowo różne.

---

## 53.1 Administrator

Administratorzy mogą:

```text id="n4x7pa"
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

Operacje tylko dla administratora obejmują zarządzanie użytkownikami i administrację rolami.

---

## 53.2 Operator

Operatorzy mogą:

```text id="b7c2mz"
View clients
View installed software
View available updates
Create and execute update jobs
View update history
Use package management
Use system maintenance
```

Operatorzy nie mogą:

```text id="q8v3kd"
Manage users
Manage roles
Create or disable clients
Rotate client tokens
```

---

## 53.3 Viewer

Viewerzy mają celowo ograniczony dostęp.

Viewer może:

```text id="y5m2rx"
View clients
View installed software
```

Następująca funkcjonalność jest ukryta w interfejsie Viewera i blokowana po stronie serwera:

```text id="e8c4nw"
Available Updates
Update Jobs
Update History
Package Management
System Maintenance
```

Jest to zamierzona kontrola bezpieczeństwa.

Jeśli Viewer może uzyskać dostęp do jednej z tych funkcji, problem należy traktować jako problem z RBAC, a nie tylko jako problem z interfejsem użytkownika.

---

# 54. Viewer widzi zbyt wiele

Jeśli Viewer widzi funkcjonalność, która nie powinna być dostępna, sprawdź obie warstwy:

```text id="x5j3mq"
Browser UI
    +
Server-side authorization
```

Ukrycie elementu w JavaScript lub HTML nie jest wystarczającym zabezpieczeniem.

API musi również odrzucać nieautoryzowane operacje.

Podczas badania:

1. Ustal rolę uwierzytelnionego użytkownika.
2. Zidentyfikuj dotknięty endpoint.
3. Sprawdź odpowiedź serwera.
4. W razie potrzeby sprawdź logi aplikacji.
5. Zweryfikuj odpowiedni test RBAC.

Nie rozwiązuj problemu autoryzacji przez samo ukrycie elementu interfejsu użytkownika.

---

# 55. Viewer nie widzi oczekiwanych danych

Viewer powinien nadal mieć dostęp do informacji wyraźnie dozwolonych przez bieżący model RBAC.

Jeśli brakuje dozwolonych informacji o klientach:

```text id="3h6q8f"
Verify login
   ↓
Verify role
   ↓
Verify client visibility
   ↓
Inspect API response
   ↓
Inspect browser console if necessary
```

Nie przyznawaj dodatkowych uprawnień tylko dlatego, że strona wydaje się obecnie niekompletna.

Najpierw ustal, czy brakujące informacje są celowo ograniczone.

---

# 56. Operator nie może wykonać operacji

Jeśli Operator otrzymuje `403 Forbidden`, najpierw ustal, czy żądane działanie jest przeznaczone tylko dla administratora.

Dostęp Operatora nie obejmuje:

```text id="n5y7cu"
User management
Role administration
Client creation/deactivation
Client token rotation
```

Jeśli operacja powinna być dozwolona dla Operatorów, sprawdź dekorator autoryzacji endpointu i odpowiednie testy RBAC.

Nie promuj tymczasowo użytkownika do Administratora jako skrótu diagnostycznego.

---

# 57. Administrator nie może wykonać operacji

Administrator powinien mieć dostęp do wszystkich obecnie obsługiwanych operacji administracyjnych.

Jeśli Administrator otrzymuje błąd autoryzacji:

```text id="q7d2nv"
Verify authenticated session
        ↓
Verify current role
        ↓
Verify endpoint authorization
        ↓
Inspect CSRF requirements
        ↓
Inspect application logs
```

Dla operacji zmieniających stan sama ważna sesja może nie być wystarczająca.

Ochrona CSRF musi być również spełniona, gdy jest wymagana.

---

# 58. Zarządzanie użytkownikami

Zarządzanie użytkownikami jest ograniczone do Administratorów.

Przepływ zarządzania użytkownikami to:

```text id="x4j6pw"
Administrator
    │
    ▼
User Management
    │
    ├── Create user
    ├── Assign role
    └── Enable / disable user
```

Gdy nie można utworzyć użytkownika, sprawdź:

```text id="b3q9fz"
Current role
Username validation
Role validation
Duplicate username
Password validation
CSRF protection
Application logs
```

Nie twórz użytkowników bezpośrednio w SQLite.

Bezpośrednie wstawianie do bazy danych omija hashowanie haseł, walidację, autoryzację i logowanie audytowe.

---

# 59. Tworzenie użytkownika zawodzi

Jeśli tworzenie użytkownika zawodzi, sprawdź odpowiedź przeglądarki i logi serwera.

API powinno zweryfikować:

```text id="7x3m5n"
Username
Role
Password requirements
Duplicate account
Authenticated administrator
CSRF token
```

Jeśli żądanie zostanie odrzucone, ustal, która reguła walidacji została uruchomiona.

Nie osłabiaj walidacji tylko po to, by jedno żądanie utworzenia konta zakończyło się sukcesem.

---

# 60. Problemy z hasłami

LUMS przechowuje hasła użytkowników przy użyciu mechanizmu hashowania haseł, a nie haseł w postaci jawnej.

Jeśli użytkownik nie może się zalogować:

```text id="9w3r5b"
Verify username
   ↓
Verify account enabled state
   ↓
Verify password
   ↓
Check login rate limiting
   ↓
Inspect authentication logs
```

Nigdy nie przechowuj ani nie loguj haseł w postaci jawnej.

Nie kopiuj haseł do poleceń diagnostycznych ani plików logów.

---

# 61. Wyłączone konto użytkownika

Wyłączonego konta nie należy traktować jako aktywnego konta logowania.

Jeśli wyłączony użytkownik nadal może się uwierzytelnić, zbadaj:

```text id="z6t2hx"
Current account state
Authentication lookup
Session state
Session revocation
Browser session
Server-side authorization
```

Nie usuwaj po prostu konta.

Zachowanie konta może być ważne dla historii audytu.

---

# 62. Problemy z sesjami

LUMS używa obsługi sesji po stronie serwera.

Gdy użytkownik wydaje się mieć nieaktualny lub nieoczekiwany dostęp, najpierw wyloguj się i ustanów nową sesję.

Jeśli problem nadal występuje, zbadaj:

```text id="q1y7vm"
Account state
Role
Session state
Session revocation
Cookie configuration
CSRF protection
```

Nie wyłączaj mechanizmów bezpieczeństwa sesji, aby obejść problem z logowaniem.

---

# 63. Unieważnianie sesji

Unieważnianie sesji jest istotne, gdy:

```text id="4n8z7p"
A password changes
A user is disabled
A role changes
A session must be invalidated
A security event requires forced logout
```

Jeśli użytkownik wydaje się zachowywać dostęp po zmianie konta, ustal, czy istniejąca sesja została poprawnie unieważniona.

Przetestuj przy użyciu nowej sesji przeglądarki dopiero po potwierdzeniu stanu konta.

Nie zakładaj, że usunięcie plików cookie przeglądarki samo w sobie dowodzi, że unieważnianie sesji po stronie serwera działa.

---

# 64. Ograniczanie szybkości logowania

LUMS stosuje ograniczanie szybkości logowania dla powtarzających się nieudanych prób uwierzytelniania.

Obecne zachowanie używa rosnących interwałów blokady:

```text id="p7k4xz"
5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

Stan niepowodzenia jest utrwalany w SQLite.

Jeśli próby logowania są nieoczekiwanie blokowane, sprawdź stan uwierzytelniania przed zmianą bazy danych.

Odpowiedź ogranicznika szybkości nie jest automatycznie błędem uwierzytelniania.

Może wskazywać, że konto osiągnęło skonfigurowany próg nieudanych prób.

---

# 65. Logowanie działa, ale API zwraca `403`

Pomyślne logowanie dowodzi uwierzytelnienia, a nie autoryzacji.

Odpowiedź `403 Forbidden` może wskazywać:

```text id="m9c2vx"
Insufficient role
Missing CSRF protection
Disallowed operation
Disabled functionality
```

Zidentyfikuj dokładny endpoint przed zmianą czegokolwiek.

Prawidłowe pytanie diagnostyczne to:

```text id="0q4g1k"
"Is this user authenticated?"
```

a następnie:

```text id="x8v5md"
"Is this authenticated user authorized for this operation?"
```

To są oddzielne kontrole bezpieczeństwa.

---

# 66. Błędy CSRF

Żądania przeglądarki zmieniające stan są chronione przed fałszowaniem żądań między witrynami.

Jeśli żądanie zmieniające stan nieoczekiwanie zawodzi:

```text id="6z4qpn"
Verify authenticated session
        ↓
Verify CSRF token
        ↓
Verify request method
        ↓
Verify endpoint
        ↓
Inspect server response
```

Nie wyłączaj ochrony CSRF jako obejścia do rozwiązywania problemów.

Nieudana kontrola CSRF jest mechanizmem bezpieczeństwa działającym zgodnie z przeznaczeniem.

---

# 67. Interfejs przeglądarki i API są niezgodne

Jeśli interfejs użytkownika pokazuje, że akcja jest dostępna, ale API ją odrzuca:

```text id="v8n3ty"
Browser UI
   ↓
Displayed role/state
   ↓
API request
   ↓
Server-side authorization
```

Wynik po stronie serwera jest autorytatywny.

Interfejs użytkownika może zawierać nieaktualny stan po:

```text id="4g7m2x"
Role changes
Session changes
Client changes
Page remains open for a long time
```

Przeładuj stronę i ustanów nową sesję, zanim założysz, że autoryzacja po stronie serwera jest nieprawidłowa.

---

# 68. Macierz diagnostyczna RBAC

| Objaw                               | Pierwszy komponent do sprawdzenia          |
| ----------------------------------- | ------------------------------------------ |
| Viewer widzi interfejs zarządzania  | Obsługa roli na stronie klienta            |
| Żądanie API Viewera kończy się sukcesem | RBAC po stronie serwera                |
| Operator otrzymuje `403`            | Model uprawnień endpointu                  |
| Administrator otrzymuje `403`       | Sesja / CSRF / autoryzacja endpointu       |
| Nie można utworzyć użytkownika      | Rola administratora + walidacja            |
| Wyłączony użytkownik może się zalogować | Stan konta + obsługa sesji             |
| Logowanie tymczasowo zablokowane    | Ograniczanie szybkości                     |
| Żądanie zmieniające stan odrzucone  | CSRF / sesja                               |
| Interfejs użytkownika i API niezgodne | Stan przeglądarki + autoryzacja serwera  |

Wynik autoryzacji po stronie serwera jest zawsze ważniejszy niż to, czy element interfejsu jest widoczny.

---

# 69. Następny obszar rozwiązywania problemów

Następne obszary diagnostyczne to:

```text id="8r5w2q"
Application and audit logging
Container security
Filesystem permissions
Docker runtime configuration
Tests and CI
Diagnostic snapshots
Final recovery checklist
```

Te obszary należy badać bez osłabiania podstaw bezpieczeństwa.

# 70. Logowanie aplikacji

LUMS używa logowania aplikacji do dostarczania informacji diagnostycznych bez ujawniania wrażliwych poświadczeń.

Podczas badania problemu z aplikacją zacznij od najnowszych logów:

```bash id="f6m2qa"
sudo docker logs \
    --tail 200 \
    lums
```

Do ciągłego monitorowania:

```bash id="x3v8kp"
sudo docker logs \
    -f \
    lums
```

W miarę możliwości odtwórz problem podczas monitorowania logów.

Ułatwia to skorelowanie:

```text id="p8k4zw"
User action
    ↓
HTTP request
    ↓
Application event
    ↓
Database operation
    ↓
Agent interaction
```

---

# 71. Logi aplikacji zawierają błąd

Najpierw zidentyfikuj komponent, który wygenerował komunikat.

Typowe źródła obejmują:

```text id="w4c8rn"
Flask application
Gunicorn
Database layer
Authentication
Authorization
Package management
Job execution
Client reporting
```

Nie zakładaj, że ostatni komunikat logu jest główną przyczyną.

Szukaj pierwszego istotnego błędu w sekwencji zdarzeń.

W miarę możliwości skoreluj:

```text id="n6q2vy"
Timestamp
Client
Request
Job ID
Error
Result
```

---

# 72. Logowanie audytowe

LUMS zapisuje istotne dla bezpieczeństwa działania aplikacji w logu audytowym.

Logowanie audytowe jest przydatne podczas badania:

```text id="j8r4px"
User changes
Authentication events
Administrative actions
Client management
Token operations
Update-job creation
Security-relevant state changes
```

Zdarzenie audytowe należy traktować jako dowód zdarzenia aplikacji, a nie jako zamiennik logów systemowych.

Używaj logów aplikacji do szczegółów technicznych wykonania, a logów audytowych do istotnych dla bezpieczeństwa działań aplikacji.

---

# 73. Brak zdarzenia audytowego

Jeśli brakuje oczekiwanego zdarzenia audytowego:

1. Zidentyfikuj dokładną akcję.
2. Zidentyfikuj endpoint API.
3. Sprawdź, czy akcja faktycznie dotarła do serwera.
4. Sprawdź logi aplikacji.
5. Ustal, czy akcja została odrzucona, zanim zdarzenie audytowe powinno zostać utworzone.

Nie wstawiaj ręcznie rekordów audytu tylko po to, by ścieżka audytu wyglądała na kompletną.

Rekord audytu powinien odpowiadać rzeczywistemu zdarzeniu aplikacji.

---

# 74. Log audytowy i log aplikacji różnią się

Dwa systemy logowania mają różne przeznaczenie.

Na przykład:

```text id="7q2m5k"
Application log
→ technical execution information

Audit log
→ security-relevant application event
```

Błąd menedżera pakietów może więc pojawić się w logu aplikacji lub Agenta, nie reprezentując oddzielnego administracyjnego zdarzenia audytowego.

Odwrotnie, działanie zarządzania użytkownikami powinno wygenerować audytowalne zdarzenie aplikacji, nawet jeśli sama operacja jest technicznie prosta.

---

# 75. Wrażliwe informacje w logach

Nigdy celowo nie umieszczaj w danych wyjściowych diagnostycznych:

```text id="3m7v9x"
Client tokens
Application secret keys
Passwords
Session secrets
Private keys
TLS private material
```

Jeśli polecenie diagnostyczne ujawniłoby jedną z tych wartości, użyj zamiast tego kontroli z redakcją lub tylko metadanych.

Podczas udostępniania logów do rozwiązywania problemów przejrzyj je pod kątem sekretów przed skopiowaniem do zgłoszeń, dokumentacji, problemów GitHub lub czatu.

---

# 76. Bezpieczeństwo kontenera Docker

Produkcyjny kontener LUMS jest celowo utwardzony.

Oczekiwane właściwości bezpieczeństwa obejmują:

```text id="z4w6pt"
Non-root application user
Read-only root filesystem
All Linux capabilities dropped
no-new-privileges enabled
No privileged mode
Dedicated writable data volume
Read-only secret mount
Restricted temporary filesystems
```

Jeśli jedna z tych właściwości zmieni się nieoczekiwanie, traktuj to jako dryf konfiguracji.

Nie osłabiaj kontenera, aby rozwiązać problem z aplikacją, chyba że wpływ na bezpieczeństwo został wyraźnie oceniony.

---

# 77. Weryfikacja bezpieczeństwa runtime kontenera

Sprawdź kontener:

```bash id="b8x5jq"
sudo docker inspect lums
```

Aby uzyskać skoncentrowaną kontrolę runtime:

```bash id="r3n7cw"
sudo docker inspect \
    --format='ReadonlyRootfs={{.HostConfig.ReadonlyRootfs}} Privileged={{.HostConfig.Privileged}} CapDrop={{json .HostConfig.CapDrop}} SecurityOpt={{json .HostConfig.SecurityOpt}}' \
    lums
```

Oczekiwane wartości obejmują:

```text id="k5m2zr"
ReadonlyRootfs=true
Privileged=false
CapDrop=[ALL]
SecurityOpt=[no-new-privileges:true]
```

Dokładne formatowanie może się różnić między wersjami Docker.

Liczą się same właściwości bezpieczeństwa.

---

# 78. Kontener działa jako root

Aplikacja LUMS powinna działać jako dedykowany użytkownik aplikacji bez uprawnień.

Jeśli kontener nieoczekiwanie działa jako root, najpierw sprawdź obraz i konfigurację runtime:

```bash id="p6x4nz"
sudo docker inspect \
    --format='{{.Config.User}}' \
    lums
```

Następnie sprawdź Dockerfile.

Nie rozwiązuj problemów z uprawnieniami aplikacji przez przełączenie produkcyjnego kontenera na root.

Jeśli katalog wymaga dostępu do zapisu, zidentyfikuj dokładną ścieżkę i ustal, czy powinna to być trwała danych aplikacji, czy dane tymczasowe.

---

# 79. System plików głównych tylko do odczytu

Produkcyjny kontener używa systemu plików głównych tylko do odczytu.

Chroni to obraz aplikacji przed niepotrzebną modyfikacją w czasie działania.

Jeśli aplikacja zgłasza:

```text id="y5k8mc"
Read-only filesystem
Permission denied
Cannot create file
Cannot write temporary data
```

najpierw ustal, **gdzie** aplikacja próbuje zapisywać.

Oczekiwane lokalizacje zapisywalne są celowo ograniczone.

Trwałe dane aplikacji należą do:

```text id="q9m3xr"
/var/lib/lums
```

Tymczasowe dane runtime mogą używać skonfigurowanych tymczasowych systemów plików.

Nie wyłączaj `--read-only` tylko dlatego, że ścieżka aplikacji jest nieoczekiwanie zapisywalna.

---

# 80. `/tmp` nie jest zapisywalny

Jeśli aplikacja wymaga miejsca tymczasowego, sprawdź tymczasowy system plików:

```bash id="a7w4vn"
sudo docker inspect \
    --format='{{json .HostConfig.Tmpfs}}' \
    lums
```

Produkcyjny kontener zapewnia ograniczony `/tmp`.

Tymczasowy system plików jest przeznaczony wyłącznie na dane przejściowe.

Trwałe dane nie mogą być tam przechowywane.

---

# 81. Problemy z montowaniem sekretów

Sekret aplikacji LUMS jest dostarczany przez chronione montowanie pliku.

Sekret nie powinien być osadzany bezpośrednio w obrazie.

Jeśli LUMS zgłasza brakujący sekret, najpierw sprawdź konfigurację runtime:

```bash id="j4p7zx"
sudo docker inspect \
    lums
```

Sprawdź, czy montowanie sekretu istnieje i jest tylko do odczytu.

Nie wypisuj zawartości sekretu.

Przydatną diagnostyką jest sprawdzenie, czy plik istnieje i ma oczekiwane uprawnienia, bez wyświetlania jego zawartości.

---

# 82. Brak pliku sekretu

Je?li plik sekretu nie istnieje na ho?cie i nie ustawiono zapasowej warto?ci `LUMS_SECRET_KEY`, aplikacja natychmiast ko?czy uruchamianie b??dem `RuntimeError: LUMS secret is not configured. Provide LUMS_SECRET_KEY_FILE or LUMS_SECRET_KEY.` (`server/app.py`). Jest to b??d uruchamiania, a nie tylko objaw problemu z uwierzytelnianiem. Szczeg??y dotycz?ce zapasowej warto?ci z pliku lub zmiennej znajduj? si? w sekcji 114.
---

# 83. Trwały wolumen nie jest zapisywalny

Jeśli LUMS nie może zapisywać danych aplikacji, sprawdź wolumen:

```bash id="y6c2mt"
sudo docker volume inspect \
    lums-data
```

Następnie sprawdź montowania kontenera:

```bash id="e5w8rq"
sudo docker inspect \
    --format='{{json .Mounts}}' \
    lums
```

Baza danych aplikacji musi znajdować się na trwałym, zapisywalnym wolumenie.

Nie czyń całego systemu plików kontenera zapisywalnym jako obejścia.

Prawidłowym rozwiązaniem jest zidentyfikowanie konkretnej ścieżki wymagającej trwałości.

---

# 84. Kontener Docker uruchamia się, ale aplikacja zawodzi

Jeśli kontener uruchamia się i natychmiast kończy:

```bash id="t7x3mp"
sudo docker ps -a \
    --filter name=lums
```

Następnie sprawdź:

```bash id="n4q6vz"
sudo docker logs \
    --tail 200 \
    lums
```

Typowe przyczyny obejmują:

```text id="w3j8kc"
Application startup error
Missing secret
Database initialization error
Migration failure
Invalid environment configuration
Permission problem
Dependency problem
```

Nie przebudowuj natychmiast obrazu.

Ustal, czy problem dotyczy obrazu, konfiguracji runtime, trwałych danych czy konfiguracji zewnętrznej.

---

# 85. Obraz Docker vs. konfiguracja kontenera

Działający obraz może nadal zawodzić z powodu nieprawidłowej konfiguracji runtime.

Zawsze rozróżniaj:

```text id="s7q2mj"
Docker image
    +
Container runtime configuration
    +
Persistent volume
    +
Secret/configuration
```

Na przykład:

```text id="m5v9rz"
Image is valid
      +
Wrong volume
      =
Application failure
```

lub:

```text id="r6c3pk"
Image is valid
      +
Missing secret
      =
Application startup failure
```

Nie przebudowuj w przeciwnym razie ważnego obrazu, aby naprawić problem z konfiguracją runtime.

---

# 86. Problemy z budowaniem Docker

Jeśli nie można zbudować nowego obrazu, najpierw sprawdź Dockerfile.

Sprawdź obraz bazowy i definicje zależności.

Produkcyjny Dockerfile używa przypiętego skrótu obrazu bazowego Python.

Zapewnia to powtarzalność i zapobiega cichemu przejściu kompilacji do niepowiązanej wersji obrazu bazowego.

Jeśli kompilacja nagle zmieni zachowanie, porównaj:

```text id="e3y7pn"
Dockerfile
Base-image digest
Requirements
Application source
Build context
```

---

# 87. Problemy z `.dockerignore`

Kontekst kompilacji Docker nie powinien zawierać niepotrzebnych plików lokalnych ani wrażliwych materiałów.

Repozytorium używa `.dockerignore` do wykluczenia plików takich jak:

```text id="k2x8vw"
Local backups
Temporary files
Editor artifacts
Backup copies
Other unnecessary runtime material
```

Jeśli kompilacja nieoczekiwanie zawiera plik, który nie powinien być obecny, sprawdź:

```bash id="q5m8cz"
cat .dockerignore
```

Nie rozwiązuj problemów z kontekstem kompilacji przez kopiowanie wrażliwych plików do obrazu.

---

# 88. Problemy z uprawnieniami systemu plików

Jeśli LUMS zgłasza błędy uprawnień, najpierw zidentyfikuj dokładną ścieżkę.

Przydatne informacje:

```bash id="p4r7yn"
sudo docker inspect \
    lums
```

oraz:

```bash id="n8v2km"
sudo docker logs \
    --tail 200 \
    lums
```

Ważne rozróżnienie to:

```text id="x6c9pw"
Application data
Temporary data
Application source
Secret material
Host configuration
```

Każdy ma inne oczekiwane uprawnienia.

Nie zmieniaj rekurencyjnie własności ani uprawnień w całym systemie plików jako skrótu do rozwiązywania problemów.

---

# 89. Dryf konfiguracji produkcyjnej

Dryf konfiguracji występuje, gdy działające środowisko nie odpowiada zamierzonej podstawie bezpieczeństwa.

Przykłady obejmują:

```text id="r5j8tx"
Container runs as root
Port 5050 exposed externally
Read-only filesystem disabled
Capabilities restored
Privileged mode enabled
Secret mounted read-write
Unexpected container running
```

Jeśli wykryto dryf:

1. Zapisz bieżący stan.
2. Ustal, kiedy się zmienił.
3. Zidentyfikuj odpowiedzialną konfigurację.
4. Popraw konfigurację celowo.
5. Ponownie uruchom odpowiednią weryfikację bezpieczeństwa.

Nie wprowadzaj kilku niepowiązanych zmian naraz.

---

# 90. Nieoczekiwana ekspozycja sieciowa

Port aplikacji powinien pozostać lokalny:

```text id="n7w4cp"
127.0.0.1:5050
```

Sprawdź nasłuchy:

```bash id="y2m6vk"
sudo ss -lntp
```

Jeśli `5050` jest wystawiony na adresie innym niż loopback, natychmiast zbadaj mapowanie portów Docker.

Nie wystawiaj portu aplikacji tylko dlatego, że Nginx wydaje się trudny do zdiagnozowania.

Zamierzona architektura to:

```text id="h3x8qm"
Network
   ↓
Nginx :443
   ↓
127.0.0.1:5050
   ↓
LUMS
```

---

# 91. Nieoczekiwane kontenery Docker

Wyświetl wszystkie kontenery:

```bash id="c6w9rz"
sudo docker ps -a
```

Nieoczekiwane kontenery należy zidentyfikować przed ich usunięciem.

Sprawdź:

```text id="m8x2kf"
Container name
Image
Creation time
Ports
Volumes
Restart policy
```

Nie usuwaj nieznanego kontenera bez ustalenia, czy jest częścią wdrożenia LUMS, czy wymaganym środowiskiem awaryjnym.

---

# 92. Wolumen Docker nie może być usuwany podczas normalnego rozwiązywania problemów

Następująca operacja jest destrukcyjna:

```bash id="q7v3mc"
sudo docker volume rm lums-data
```

Nie może być używana jako ogólny krok rozwiązywania problemów.

Usunięcie wolumenu może usunąć bazę danych aplikacji i powiązany trwały stan.

Jeśli czysta instalacja jest celowo wymagana, traktuj ją jako oddzielną operację migracji lub odzyskiwania i najpierw zweryfikuj kopie zapasowe.

---

# 93. Podstawa bezpieczeństwa po zmianach runtime

Po zmianie produkcyjnej konfiguracji Docker ponownie zweryfikuj podstawę bezpieczeństwa.

Należy co najmniej zweryfikować:

```text id="z5n8xp"
Container runs as intended user
Root filesystem is read-only
Capabilities are dropped
Privileged mode is disabled
no-new-privileges is enabled
Secret mount is read-only
Database volume is writable
Application port is loopback-only
```

Konfiguracja, która sprawia, że aplikacja działa, ale osłabia te właściwości, nie powinna być uważana za udaną naprawę.

---

# 94. Następny obszar rozwiązywania problemów

Pozostałe tematy rozwiązywania problemów to:

```text id="v4m7yx"
Tests and CI
Diagnostic snapshots
Common failure combinations
Recovery principles
Final troubleshooting checklist
```

Ostatnie sekcje zawierają zwięzłą procedurę zbierania wystarczających informacji do zdiagnozowania problemu bez niepotrzebnej zmiany środowiska produkcyjnego.

# 95. Testy i CI

Testy automatyczne są ważną częścią rozwiązywania problemów z LUMS.

Przed zbadaniem problemu produkcyjnego jako defektu aplikacji sprawdź, czy odpowiednie zachowanie jest już objęte zestawem testów.

Obecny pełny zestaw testów powinien przechodzić, zanim wydanie zostanie uznane za gotowe.

Uruchom pełny zestaw testów z repozytorium:

```bash id="m4x8kp"
./.venv-test/bin/pytest -q
```

Pomyślne uruchomienie powinno zgłosić wszystkie testy jako zaliczone.

Liczba testów zmienia się w miarę dodawania kolejnych testów. Ważnym
warunkiem jest to, że pełny zestaw testów kończy się sukcesem, a nie poleganie na
stałej liczbie testów.

---

# 96. Niepowodzenie testu nie oznacza automatycznie, że produkcja jest zepsuta

Nieudany test może być spowodowany przez:

```text id="q8r5wy"
Application regression
Test regression
Dependency change
Environment problem
Missing test dependency
Incorrect test configuration
```

Najpierw sprawdź pełne dane wyjściowe niepowodzenia.

Nie modyfikuj konfiguracji produkcyjnej tylko dlatego, że lokalny test zawodzi.

Prawidłowa sekwencja to:

```text id="n4m7tx"
Test failure
    ↓
Read complete error
    ↓
Identify affected component
    ↓
Reproduce locally
    ↓
Determine root cause
    ↓
Apply controlled fix
    ↓
Run relevant tests
    ↓
Run full test suite
```

---

# 97. Niepowodzenia testów RBAC

Podczas badania problemów z autoryzacją najpierw uruchom testy RBAC:

```bash id="k6w2pv"
./.venv-test/bin/pytest -q tests/test_rbac.py
```

Testy obejmują zachowanie specyficzne dla roli i granice autoryzacji.

Jeśli problem dotyczy strony klienta, użyj odpowiedniego podzbioru, gdy jest to właściwe:

```bash id="z5n8rc"
./.venv-test/bin/pytest -q \
    tests/test_rbac.py -k client_page
```

Nie osłabiaj autoryzacji, aby test przeszedł.

Nieudany test autoryzacji może wskazywać na regresję bezpieczeństwa.

---

# 98. Niepowodzenia testów wyszukiwania pakietów

Funkcjonalność zarządzania pakietami ma dedykowane pokrycie testowe.

Podczas badania zachowania wyszukiwania pakietów:

```bash id="b7x3mf"
./.venv-test/bin/pytest -q \
    tests/test_package_search.py
```

Jeśli niepowodzenie dotyczy wykonywania pakietów lub wyników zadań, sprawdź również odpowiednie testy wyników zadań.

Zestaw testów powinien służyć do rozróżnienia:

```text id="y9r4nk"
Application logic problem
Package-search problem
Agent problem
Integration problem
```

---

# 99. Testy walidacji wyników zadań

Obsługa wyników zadań jest wrażliwa na bezpieczeństwo, ponieważ serwer nie może bezrefleksyjnie ufać dowolnym danym wejściowym klienta.

Uruchom odpowiednie testy podczas badania walidacji wyników:

```bash id="w6q2vz"
./.venv-test/bin/pytest -q \
    tests/test_job_result.py
```

Niepowodzenie tutaj należy traktować jako problem poprawności i bezpieczeństwa aplikacji.

Nie omijaj walidacji wyników, aby raport klienta zakończył się sukcesem.

---

# 100. Niepowodzenia CI

LUMS używa ciągłej integracji do weryfikacji projektu przed zaakceptowaniem zmian.

Jeśli CI zawodzi:

1. Zidentyfikuj nieudane zadanie.
2. Przeczytaj pełny błąd.
3. Ustal, czy niepowodzenie jest związane z kodem, zależnością, testem czy środowiskiem.
4. W miarę możliwości odtwórz lokalnie.
5. Napraw główną przyczynę.
6. Uruchom odpowiednie testy.
7. Uruchom pełny zestaw testów.

Nie ignoruj niepowodzeń CI tylko dlatego, że środowisko produkcyjne wydaje się obecnie działać.

---

# 101. Migawka diagnostyczna

Prosząc o pomoc z problemem LUMS, zbierz minimalną migawkę diagnostyczną.

Celem jest dostarczenie wystarczających informacji do zidentyfikowania zawodzącego komponentu bez ujawniania sekretów.

Przydatna migawka obejmuje:

```bash id="x8p4qn"
sudo docker ps
```

```bash id="c5m7vz"
sudo docker logs --tail 100 lums
```

```bash id="f2w9yk"
sudo systemctl status nginx --no-pager
```

```bash id="n6r3tx"
sudo systemctl status lums-agent.service --no-pager
```

```bash id="q7v4mc"
sudo systemctl status lums-agent-watcher.service --no-pager
```

```bash id="z3k8wp"
sudo journalctl -u lums-agent.service -n 100 --no-pager
```

```bash id="h5m2rx"
sudo journalctl -u lums-agent-watcher.service -n 100 --no-pager
```

```bash id="p9x6kc"
sudo ss -lntp
```

Używaj tylko poleceń odpowiednich do problemu.

Nie zrzucaj całego środowiska do prośby o wsparcie.

---

# 102. Migawka diagnostyczna nie może zawierać sekretów

Przed udostępnieniem danych wyjściowych diagnostycznych sprawdź:

```text id="r4m8yn"
Passwords
Client tokens
Application secret keys
Session secrets
Private keys
TLS private material
Credentials
```

Zredaguj wrażliwe wartości przed udostępnieniem.

Nie zakładaj, że log jest bezpieczny tylko dlatego, że pochodzi z usługi systemowej.

---

# 103. Macierz kombinacji awarii

Niektóre objawy stają się łatwiejsze do zdiagnozowania, gdy rozważy się kilka komponentów razem.

| Objaw                                         | Najbardziej prawdopodobny obszar do sprawdzenia jako pierwszy |
| --------------------------------------------- | ------------------------------------------------------------ |
| Przeglądarka nie może się połączyć            | Nginx / TLS / sieć                                           |
| Nginx działa, ale aplikacja zawodzi           | Docker / LUMS                                                |
| LUMS działa, ale klient nie może raportować   | Agent / TLS / token                                          |
| Klient raportuje, ale zadanie pozostaje oczekujące | Watcher / kwalifikowalność                              |
| Zadanie działa, ale pakiet zawodzi            | APT / pacman                                                 |
| Pakiet się powodzi, ale brak wyniku           | Raportowanie Agenta                                          |
| Wynik dociera do serwera, ale interfejs użytkownika jest nieaktualny | API / baza danych / stan przeglądarki |
| Viewer może modyfikować dane                  | RBAC po stronie serwera                                      |
| Użytkownik nie może się zalogować             | Konto / hasło / ograniczanie szybkości                       |
| Logowanie działa, ale akcja jest odrzucana    | RBAC / CSRF                                                  |
| Zapisy do bazy danych zawodzą                 | SQLite / dysk / uprawnienia                                  |
| Kontener traci dane po odtworzeniu            | Konfiguracja trwałego wolumenu                               |
| Aplikacja zapisuje do systemu plików głównych | Konfiguracja systemu plików kontenera                        |
| Port 5050 jest osiągalny z zewnątrz           | Konfiguracja Docker / firewalla                              |

Ta tabela wskazuje pierwsze miejsce do zbadania, a niekoniecznie ostateczną przyczynę.

---

# 104. Typowe błędy w rozwiązywaniu problemów

Unikaj następujących skrótów:

## Nie usuwaj bazy danych

```text id="h7k2px"
Deleting lums.db
Deleting lums-data
```

może zniszczyć trwały stan aplikacji.

---

## Nie wyłączaj mechanizmów bezpieczeństwa

Nie wyłączaj trwale:

```text id="j5r9cw"
RBAC
CSRF protection
TLS validation
Container hardening
Read-only filesystem
no-new-privileges
Capability restrictions
```

Obejście, które usuwa mechanizm bezpieczeństwa, nie jest zakończoną naprawą.

---

## Nie uruchamiaj kontenera jako uprzywilejowany

Unikaj:

```text id="b3x7mz"
--privileged
```

jako rozwiązania problemu.

Jeśli aplikacja wymaga dodatkowego dostępu, ustal dokładnie, jaki dostęp jest wymagany.

---

## Nie wystawiaj portu 5050

Nie zmieniaj:

```text id="v8n4qr"
127.0.0.1:5050
```

na:

```text id="p2m6wy"
0.0.0.0:5050
```

tylko po to, by obejść Nginx.

Aplikacja jest celowo chroniona za reverse proxy.

---

## Nie modyfikuj ręcznie stanów zadań

Unikaj bezpośredniej zmiany:

```text id="r7c5xn"
update_jobs
update_job_packages
```

aby ukryć problem operacyjny.

Używaj mechanizmów aplikacji, Agenta, watchera i odzyskiwania.

---

## Nie usuwaj bezrefleksyjnie blokad menedżera pakietów

Blokada może wskazywać na aktywny proces menedżera pakietów.

Najpierw zidentyfikuj proces.

---

## Nie rotuj poświadczeń wielokrotnie

Powtarzająca się rotacja tokenów lub sekretów może stworzyć dodatkowe problemy z uwierzytelnianiem.

Najpierw ustal, które poświadczenie jest obecnie skonfigurowane i którego poświadczenia oczekuje serwer.

---

# 105. Zasady odzyskiwania

Następujące zasady mają zastosowanie do wszystkich działań związanych z rozwiązywaniem problemów LUMS:

### Najpierw zachowaj

Zachowaj:

```text id="q3m8vx"
Logs
Job state
Database
Container state
Configuration
Error messages
```

dopóki problem nie zostanie zrozumiany.

### Zmieniaj jedną rzecz naraz

Gdy kilka zmian jest wprowadzanych jednocześnie, pierwotna przyczyna staje się trudniejsza do zidentyfikowania.

### Weryfikuj po każdej zmianie

Po kontrolowanej zmianie:

```text id="z6w2kp"
Re-test
Check logs
Verify state
Confirm security properties
```

### Preferuj zmiany odwracalne

W miarę możliwości używaj zmian, które można cofnąć bez niszczenia stanu aplikacji.

### Utrzymuj aktywne mechanizmy bezpieczeństwa

Pomyślny wynik rozwiązywania problemów nie może wprowadzać niepotrzebnej regresji bezpieczeństwa.

---

# 106. Sekwencja rozwiązywania problemów produkcyjnych

Dla ogólnego problemu produkcyjnego LUMS użyj tej kolejności:

```text id="f4n8rx"
1. Identify the symptom
        ↓
2. Identify the affected component
        ↓
3. Inspect current state
        ↓
4. Inspect relevant logs
        ↓
5. Reproduce safely
        ↓
6. Determine the first failing layer
        ↓
7. Apply the smallest required change
        ↓
8. Re-test
        ↓
9. Verify security controls
        ↓
10. Document the result
```

Ta kolejność zapobiega niepotrzebnemu zmienianiu niepowiązanych komponentów.

---

# 107. Pełna ścieżka diagnostyczna systemu

Gdy dotknięty komponent jest nieznany, przejdź pełną ścieżką:

```text id="u7x3mp"
Browser
  │
  ▼
Nginx / HTTPS
  │
  ▼
Docker
  │
  ▼
LUMS API
  │
  ▼
SQLite
  │
  ▼
Update Job
  │
  ▼
Watcher
  │
  ▼
Agent
  │
  ▼
APT / pacman
  │
  ▼
Client state
  │
  ▼
Agent result
  │
  ▼
LUMS API
  │
  ▼
SQLite
  │
  ▼
Web UI
```

Na każdym etapie pytaj:

```text id="k5r2qy"
Did the request reach this component?

Did this component process it?

Did it produce the expected result?

Did the next component receive that result?
```

Pierwsze `NO` zwykle identyfikuje obszar wymagający zbadania.

---

# 108. Rozwiązywanie problemów z wydaniem

Przed przygotowaniem wydania sprawdź:

```text id="m8x4vp"
Full test suite passes
CI passes
Security audit is complete
Documentation is current
Production configuration matches the documented baseline
No unexpected debug configuration remains
No secrets are included in the repository
Docker hardening remains active
RBAC behavior is correct
Package management works
Update-job execution works
Recovery behavior is verified
```

Wydanie nie powinno być tworzone tylko dlatego, że aplikacja uruchamia się pomyślnie.

---

# 109. Lista kontrolna rozwiązywania problemów

Użyj tej listy kontrolnej przed ogłoszeniem problemu produkcyjnego jako rozwiązanego:

```text id="y6q3kn"
[ ] Root cause identified
[ ] Relevant logs inspected
[ ] No unnecessary data was deleted
[ ] No credentials were exposed
[ ] No security control was disabled
[ ] Relevant functionality tested
[ ] Full test suite considered where appropriate
[ ] Docker security baseline verified
[ ] Network exposure verified
[ ] Agent state verified
[ ] Watcher state verified
[ ] Job state verified
[ ] Recovery state verified
[ ] Database state verified where relevant
[ ] Documentation updated if behavior changed
```

---

# 110. Kiedy przestać rozwiązywać problemy

Przestań wprowadzać zmiany, gdy:

```text id="v9m4xr"
The root cause is identified
    AND
The corrective action is understood
    AND
The system is stable
    AND
Security controls remain intact
```

Jeśli główna przyczyna nie jest zrozumiana, zachowaj bieżący stan, zamiast wielokrotnie zmieniać środowisko.

Czysto zachowana awaria jest łatwiejsza do zdiagnozowania niż częściowo zmodyfikowany system.

---

# 111. Końcowa zasada odzyskiwania

Najważniejsza zasada rozwiązywania problemów LUMS to:

> **Najpierw obserwuj. Potem zmieniaj. Na końcu weryfikuj.**

LUMS zawiera kilka niezależnych warstw bezpieczeństwa i wykonania.

Problem w jednej warstwie nie powinien automatycznie skutkować zmianami w innej.

Preferowane podejście do rozwiązywania problemów to zatem:

```text id="c8w5zn"
Observe
   ↓
Classify
   ↓
Isolate
   ↓
Correct
   ↓
Verify
   ↓
Document
```

Dzięki temu rozwiązywanie problemów pozostaje kontrolowane, powtarzalne i zgodne z podstawą bezpieczeństwa LUMS.

---

# 112. Konserwacja dokumentacji

Ten dokument powinien być aktualizowany za każdym razem, gdy zmieni się udokumentowane zachowanie operacyjne.

Zmiany w dokumentacji powinny pozostać spójne z:

```text id="q7m3vx"
Security documentation
Deployment documentation
Agent behavior
Watcher behavior
RBAC model
Package-management behavior
Docker runtime configuration
Test baseline
```

Nieaktualne instrukcje rozwiązywania problemów mogą być niebezpieczne, gdy zalecają przestarzałe polecenia lub obejścia osłabiające bezpieczeństwo.

Gdy zachowanie produkcyjne się zmienia, zaktualizuj odpowiednią dokumentację, zanim procedura rozwiązywania problemów zostanie uznana za zakończoną.

---

# 113. Bie??ca podstawa

Bie??ca podstawa LUMS udokumentowana w tym przewodniku rozwi?zywania problem?w obejmuje:

```text id="m4x8qp"
Agent version: 1.7.0
Watcher version: 1.2.1

Application port:
127.0.0.1:5050

Database:
SQLite

SQLite journal mode:
WAL (enabled by server/init_db.py; verify on your database with
sqlite3 <db> "pragma journal_mode;")

SQLite busy timeout:
5000 ms

SQLite synchronous:
2

SQLite foreign keys:
Enabled by the application

Container:
Non-root
Read-only root filesystem
Capabilities dropped
no-new-privileges enabled
Privileged mode disabled

RBAC:
Administrator
Operator
Viewer

Viewer:
Clients + Installed Software only

Full test suite:
Run on Linux (the CI reference is Ubuntu with Python 3.13). Some tests
assume Linux features such as os.geteuid() or an installed apt/pacman and
can fail on Windows; check the CI result for the revision you deploy.
```

Nie traktuj tej podstawy jako dowodu prawid?owego dzia?ania konkretnej instalacji; sprawd? ka?d? warto?? w systemie docelowym.

W?a?ciwo?ci bezpiecze?stwa i architektury stanowi? istotn? podstaw?.

---

# 114. Pu?apki konfiguracji podczas uruchamiania

**Objaw:** Kontener natychmiast si? zamyka albo serwer u?ywa innej bazy danych lub katalogu kopii zapasowych, ni? sugeruje wolumen Docker.

**Fakty wynikaj?ce z kodu (`server/app.py`):**

- Bez sekretu aplikacja zg?asza `RuntimeError: LUMS secret is not configured. Provide LUMS_SECRET_KEY_FILE or LUMS_SECRET_KEY.`
- Je?li plik wskazany przez `LUMS_SECRET_KEY_FILE` nie istnieje, kod u?ywa zapasowego `LUMS_SECRET_KEY`. W ten spos?b obs?ugiwany jest wy??cznie brak pliku; nieczytelny plik (z powodu uprawnie?) mo?e zamiast tego wywo?a? b??d systemu plik?w.
- `LUMS_DB_PATH` i `LUMS_BACKUP_DIR` zast?puj? domy?lne ?cie?ki `/var/lib/lums/lums.db` i `/var/backups/lums`. Nieaktualne nadpisanie po cichu kieruje LUMS do innej lokalizacji ni? zamontowany wolumen.

**Weryfikacja (tylko do odczytu):**

```text
docker compose logs lums | grep "LUMS secret"
docker inspect lums --format '{{range .Config.Env}}{{println .}}{{end}}'
ls -l <secret file>   # permissions only; never print the contents
```

**Naprawa:** Popraw ?cie?k? sekretu lub jego uprawnienia albo usu? nieaktualne nadpisania `LUMS_DB_PATH` / `LUMS_BACKUP_DIR`. Nie generuj pochopnie nowego sekretu (zob. sekcja 82).

---

# 115. Agent nie mo?e si? uruchomi? z powodu kontroli podczas importu

**Objaw:** `lums-agent` zawodzi, zanim odczyta token, na przyk?ad z b??dem `RuntimeError: No supported package manager found. Supported package managers: apt, pacman` albo b??dem SSL dotycz?cym pliku CA.

**Przyczyna:** Podczas importowania modu?u `agent/agent.py` wykrywa mened?er pakiet?w i tworzy kontekst TLS. Hosty bez `apt` lub `pacman` (albo z brakuj?cym lub nieczytelnym `LUMS_CA_FILE`) nie uruchomi? si?. Dotyczy to r?wnie? ?rodowisk testowych, takich jak Windows.

**Weryfikacja:**

```text
systemctl status lums-agent --no-pager
journalctl -u lums-agent -n 50 --no-pager
```

**Naprawa:** U?yj obs?ugiwanej dystrybucji, sprawd?, czy mened?er pakiet?w znajduje si? w `PATH` us?ugi, oraz czy u?ytkownik us?ugi mo?e odczyta? istniej?cy `LUMS_CA_FILE`.

---

# 116. Agent u?ywa nieprawid?owego adresu serwera (port 5000 zamiast 5050)

**Objaw:** Agent zg?asza odmow? po??czenia, chocia? serwer dzia?a prawid?owo.

**Przyczyna:** Wbudowany adres domy?lny agenta to `LUMS_BASE=http://127.0.0.1:5000`, natomiast udokumentowany kontener udost?pnia `127.0.0.1:5050`. Przyk?ady z portem `5050` w tym przewodniku opisuj? port udost?pniany przez serwer, a nie warto?? domy?ln? agenta.

**Weryfikacja:**

```text
systemctl show lums-agent --property=Environment
ss -lntp | grep -E ':5000|:5050'
```

**Naprawa:** Ustaw jawnie `LUMS_BASE` na rzeczywisty punkt ko?cowy dost?pny dla klienta (zwykle adres HTTPS wdro?enia). Nie wystawiaj publicznie portu `5050` jako obej?cia.

---

# 117. Watcher ko?czy dzia?anie ze statusem 1

**Objaw:** `lums-watcher` ko?czy si? b??dem i zapisuje jeden z komunikat?w: `CLIENT LOOKUP FAILED`, `RUNNING JOB LOOKUP FAILED`, `JOB LOOKUP FAILED`, `IDLE CHECK FAILED`, `JOB CLAIM FAILED`, `UPDATE EXECUTION FAILED`.

**Przyczyna:** Watcher jest jednostk? jednorazow?. Przechwytuje ka?dy b??d, zapisuje go, ko?czy si? ze statusem 1 i nie ponawia pr?by w tym samym procesie; nast?pne uruchomienie timera zaczyna od nowa. Wznawia tylko zadania, kt?rych status to dok?adnie `running`. W przeciwnym razie szuka oczekuj?cych zada?, a `NO UPDATE JOB // SYSTEM CLEAN` to normalny wynik.

**Weryfikacja:**

```text
journalctl -u lums-watcher -n 100 --no-pager
systemctl status lums-watcher lums-watcher.timer
```

**Naprawa:** Rozwi?? wskazany problem (dost?pno?? API, token, kontrola bezczynno?ci, blokada mened?era pakiet?w) i pozw?l timerowi uruchomi? si? ponownie. Sprawdzaj stan zada? przez interfejs lub API; nigdy nie zmieniaj r?cznie ich stan?w w SQLite.

---

# 118. Host Updater stale zapisuje b??dy heartbeat

**Objaw:** `lums-host-updater` nadal dzia?a, ale wielokrotnie zapisuje `Heartbeat failed (ValueError)` lub `Heartbeat failed (HTTPError)`.

**Przyczyna:** Host Updater celowo przechwytuje b??dy w p?tli i ponawia pr?b?. Typowe przyczyny (`host_updater/agent.py`):

- `Host-updater token is missing or too short` ? plik tokena nie istnieje lub zawiera mniej ni? 32 znaki.
- `Only a loopback LUMS endpoint is permitted` ? URL musi u?ywa? `http` lub `https`, host musi mie? dok?adn? warto?? `127.0.0.1`, port musi by? podany, a dane logowania, zapytanie i fragment s? niedozwolone (np. `http://127.0.0.1:5050`).
- HTTP `401` z `host_updater_authentication_required` ? token bearer jest nieprawid?owy.
- HTTP `503` z `host_updater_not_configured` ? serwer nie skonfigurowa? tokena Host Updatera.
- Us?uga zatrzymuje si? z komunikatem `Unexpected update-execution state; stopping` (kod wyj?cia 1), gdy odpowied? heartbeat nie zawiera jawnie `update_execution_enabled: false`. Sprawd? zgodno?? wersji serwera i Host Updatera.

**Weryfikacja (nie wy?wietlaj tokena):**

```text
journalctl -u lums-host-updater -n 100 --no-pager
systemctl show lums-host-updater --property=Environment
stat /etc/lums-host-updater/token
```

**Naprawa:** Popraw w?a?ciciela i tryb pliku tokena, ustaw prawid?owy adres loopback, a nast?pnie tylko raz uruchom us?ug? ponownie.

---

# 119. ??dania integracji alert?w zwracaj? 501

**Objaw:** Konfigurowanie, testowanie lub usuwanie integracji e-mail, Slack, PagerDuty albo webhooka zwraca `501` z komunikatem `Notification integrations are disabled pending secure persistent configuration`.

**Przyczyna:** To dzia?anie jest zamierzone (`server/alerts_routes.py`). Integracje s? niedost?pne, `POST /alerts/clear-all` r?wnie? zwraca `501`, a regu?y nie s? automatycznie oceniane. Nie ponawiaj pr?by i nie wprowadzaj sekret?w dostawc?w.

**Powi?zane:** Te trasy wymagaj? `alerts.manage` i ochrony CSRF. Brakuj?cy lub nieprawid?owy token CSRF powoduje `403` z `csrf_validation_failed` przed odpowiedzi? `501`. Nie wy??czaj CSRF. Zob. `docs/LUMS_REALTIME_ALERTING_IMPLEMENTATION.md`.

---

# 120. Problemy z logowaniem: CSRF, ograniczanie pr?b i blokady

**Objaw:** Prawid?owe has?o zostaje odrzucone po kilku nieudanych pr?bach albo pojawia si? wpis audytu `login.rate_limit`.

**Przyczyna:** Pr?by logowania s? ograniczane wed?ug nazwy u?ytkownika i ?r?d?a, a stan jest przechowywany w SQLite (`login_rate_limits`, z `locked_until`), wi?c przetrwa ponowne uruchomienia. Trasa `/login` jest wy??czona z kontroli CSRF; brak tokena CSRF nie powoduje niepowodzenia logowania. Sprawd? dane uwierzytelniaj?ce, pliki cookie i ograniczenie pr?b.

**Weryfikacja (tylko do odczytu):**

```text
sqlite3 /var/lib/lums/lums.db "select rate_limit_key, locked_until from login_rate_limits;"
```

**Naprawa:** Poczekaj na wyga?ni?cie blokady i usu? ?r?d?o nieudanych pr?b. Nie usuwaj r?cznie wierszy ani nie testuj przez wielokrotne pr?by logowania.

---

# 121. SQLite jest zaj?te lub migracje trafiaj? do niew?a?ciwej bazy danych

**Objaw:** Zapisy zawodz? z powodu wsp??bie?no?ci albo migracja pozornie ko?czy si? powodzeniem, ale uruchomionemu serwerowi nadal brakuje tabel lub funkcji.

**Przyczyna:** Po??czenia aplikacji u?ywaj? `PRAGMA busy_timeout = 5000`, wi?c zapis czeka maksymalnie pi?? sekund. Baza dzia?a w trybie WAL (`server/init_db.py`), dlatego pliki `-wal` i `-shm` s? normalne. Skrypty migracji samodzielnie odczytuj? `LUMS_DB_PATH` i mog? zmodyfikowa? inny plik ni? u?ywany przez serwer.

**Weryfikacja:**

```text
sqlite3 /var/lib/lums/lums.db "pragma busy_timeout; pragma journal_mode;"
docker inspect lums --format '{{range .Config.Env}}{{println .}}{{end}}'
```

**Naprawa:** Znajd? i zatrzymaj konkuruj?cy proces, zachowaj pliki WAL i SHM oraz dostosuj ?rodowisko migracji do ?rodowiska serwera. Nigdy nie usuwaj plik?w `-wal` ani `-shm`.

---

# 122. Przywracanie odmawia dzia?ania (obecne pliki WAL/SHM)

**Objaw:** Przywracanie zatrzymuje si? z komunikatem `Restore verweigert: SQLite-WAL/SHM-Datei vorhanden.` (komunikat w kodzie jest po niemiecku).

**Przyczyna:** `server/database_backup.py` odmawia dzia?ania, je?li istniej? pliki pomocnicze docelowej bazy, aby unikn?? mieszania starych i nowych danych.

**Weryfikacja:** `find /var/lib/lums -maxdepth 1 -type f -name 'lums.db*'`

**Naprawa:** Zatrzymaj lub wstrzymaj aplikacj? i u?yj udokumentowanej procedury przywracania. Nigdy nie usuwaj r?cznie plik?w pomocniczych.

---

# 123. B??dy migawki i weryfikacji wydania

**Objawy i przyczyny (`scripts/volume_snapshot.py`, `scripts/release_verification.py`):**

| Komunikat | Znaczenie |
| --- | --- |
| `Could not create or publish the snapshot.` | Miejsce docelowe ju? istnieje lub nie mo?na w nim zapisywa?; migawki nigdy nie s? nadpisywane. |
| `Source tree changed during snapshot creation.` | Pliki zmieni?y si? podczas kopiowania; wstrzymaj zapisy i pon?w pr?b?. |
| `Invalid snapshot filename.` / `Invalid restore target.` | Odrzucono niebezpieczn? ?cie?k? lub nazw? pliku. |
| `Duplicate restore target: ...` | Archiwum zawiera zduplikowane wpisy; u?yj archiwum utworzonego obs?ugiwanym narz?dziem. |
| Weryfikacja wydania nie powiod?a si? dla danych sumy kontrolnej | Metadane sumy kontrolnej s? ograniczone do 4096 bajt?w; pobierz oficjalny plik sum kontrolnych zamiast pomija? weryfikacj?. |

Przywracanie bez uprawnie? roota celowo nie stosuje dowolnych w?a?cicieli z archiwum. Wykonaj udokumentowane przywracanie jako w?a?ciwe konto us?ugi, zamiast uruchamia? kontener jako root. Wy?wietl list? element?w poleceniem `tar -tf`, nie rozpakowuj?c archiwum.

---

# 124. Koniec przewodnika rozwi?zywania problem?w

Rozwi?zywanie problem?w LUMS powinno pozosta? oparte na dowodach i ?wiadome bezpiecze?stwa.

W razie w?tpliwo?ci:

```text id="r9x4kw"
Preserve the state.
Inspect the evidence.
Identify the failing layer.
Make the smallest safe change.
Verify the result.
Document what happened.
```

Nie po?wi?caj bezpiecze?stwa ani integralno?ci danych dla szybkiego obej?cia.

---

**Koniec przewodnika rozwi?zywania problem?w LUMS**
