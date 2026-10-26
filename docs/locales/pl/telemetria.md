# Telemetria procesora, pamięci i sieci LUMS

## Przegląd

Opcjonalny agent telemetrii LUMS zbiera z zarządzanego systemu Linux
wykorzystanie procesora i pamięci, liczniki sieciowe oraz ograniczony zestaw
informacji o hoście, a następnie wysyła pomiary do serwera LUMS.

Serwer przechowuje próbki telemetrii i udostępnia uwierzytelnione API historii,
z którego korzysta pulpit telemetrii klienta.

Telemetria jest niezależna od istniejącego agenta raportującego i procesu
Watcher LUMS. Nie zastępuje żadnego z tych komponentów ani nie wykonuje
aktualizacji pakietów.

## Komponenty

| Komponent | Odpowiedzialność |
| --- | --- |
| `agent/telemetry.py` | Zbiera metryki procesora, pamięci, hosta, sieci, czujników, usług i kontenerów |
| `agent/lums-telemetry.service` | Uruchamia agenta telemetrii jako usługę systemd z ograniczonymi uprawnieniami |
| `agent/lums-telemetry.timer` | Planuje cykliczne zbieranie telemetrii |
| `server/app.py` | Uwierzytelnia przesłane dane, sprawdza metryki i zapisuje próbki |
| `server/static/telemetry.js` | Wyświetla przegląd floty, wykresy historii i wskaźniki pierścieniowe |

## Pomiary

Każda próbka zawiera następujące wymagane pola:

- `cpu_percent`: wykorzystanie procesora w zakresie od 0 do 100.
- `memory_percent`: wykorzystanie pamięci w zakresie od 0 do 100.
- `memory_total_bytes`: wykryta całkowita ilość pamięci w bajtach.
- `memory_available_bytes`: dostępna ilość pamięci w bajtach.

Agent w wersji 1.1.0 i nowszych wysyła również dwa opcjonalne liczniki
narastające:

- `network_rx_bytes`: liczba bajtów odebranych od uruchomienia systemu,
  zsumowana dla wszystkich interfejsów innych niż loopback.
- `network_tx_bytes`: liczba bajtów wysłanych od uruchomienia systemu,
  zsumowana dla wszystkich interfejsów innych niż loopback.

Oba liczniki należy wysyłać razem jako nieujemne liczby całkowite. Starsze
agenty, które ich nie przesyłają, nadal działają; pulpit nie wyświetli wtedy
danych sieciowych dla danego klienta. Serwer zapisuje surowe liczniki i
oblicza liczbę bajtów na sekundę na podstawie kolejnych próbek podczas
żądania danych. Nie wyświetla szybkości dla pierwszej próbki, po wyzerowaniu
licznika (na przykład po ponownym uruchomieniu systemu) ani wtedy, gdy odstęp
między próbkami przekracza pięć minut.

Agent w wersji 1.2.0 i nowszych raportuje także ograniczony zestaw informacji
o systemie:

- średnie obciążenie, czas działania, system operacyjny, jądro i wykorzystanie
  głównego systemu plików;
- stan łącza, liczniki bajtów, błędy i utracone pakiety dla każdego interfejsu
  sieciowego;
- skonfigurowane serwery DNS oraz sprawdzaną w miarę możliwości dostępność
  bramy, DNS i Internetu;
- odczyty temperatury i wentylatorów, jeśli udostępnia je jądro;
- stany wybranych usług systemd, czasy ich działania i liczbę ponownych
  uruchomień, a także nazwy kontenerów Docker i Podman oraz ich
  znormalizowane stany, jeśli lokalne narzędzia i uprawnienia pozwalają na
  inspekcję tylko do odczytu;
- procent wykorzystania dysku w każdej próbce telemetrii, na potrzeby
  wykresów historycznych i oceny zdarzeń progowych.

Agent w wersji 1.3.0 i nowszych raportuje również ograniczone podsumowania
zdarzeń operacyjnych: liczbę i znaczniki czasu nieudanych logowań SSH,
ostatnią liczbę ostrzeżeń i błędów w dzienniku, znaczniki czasu logowania i
wylogowania oraz pierwszy i ostatni znacznik czasu w dzienniku dla ostatnich
uruchomień systemu. Surowe komunikaty dziennika, nazwy użytkowników i adresy
źródłowe nie są wysyłane. Każde zapytanie do dziennika obejmuje najwyżej 500
pasujących wpisów; pulpit oznacza wynik 500 jako `500+`. Historia uruchomień
systemu jest ograniczona do 10 pozycji, a historia logowań i wylogowań do 20
zdarzeń.

Serwer oblicza przepustowość poszczególnych interfejsów na podstawie kolejnych
próbek. Szczegóły usług, kontenerów, temperatur, wentylatorów i zdarzeń są
przechowywane wyłącznie jako najnowszy zestaw danych, a nie powielane w każdej
próbce historycznej. Opcjonalne metryki, których system operacyjny nie
udostępnia lub do których agent nie ma uprawnień, są oznaczane jako
niedostępne. Agent nie uruchamia, nie zatrzymuje ani nie modyfikuje usług czy
kontenerów. Usługa agenta nie otrzymuje dostępu do gniazda Docker; szczegóły
kontenerów są niedostępne, chyba że środowisko uruchomieniowe już pozwala
kontu usługi na ich inspekcję.

Jednostka systemd telemetrii należy do grupy `systemd-journal`, aby uzyskać
dostęp do dziennika wyłącznie do odczytu. Daje to dostęp do dzienników
systemowych, ale agent wysyła tylko opisane wyżej ograniczone podsumowania.
Domyślna lista dozwolonych usług obejmuje jednostki LUMS, Docker i SSH.
Można ją zastąpić wartością rozdzieloną przecinkami w zmiennej
`LUMS_MONITORED_SERVICES` w pliku środowiskowym agenta; akceptowane są
wyłącznie prawidłowe nazwy jednostek `.service`.

Dostępność bramy jest sprawdzana za pomocą pojedynczego pakietu ping, jeśli
narzędzie jest dostępne; dostępność DNS — za pomocą krótkiego zapytania
`getent`, a dostępność Internetu — krótkiej próby połączenia TCP z
`1.1.1.1:443`. Są to jedynie wskaźniki i mogą odzwierciedlać zasady zapory,
a nie awarię.

Znacznik czasu próbki nadaje serwer, który odrzuca nieprawidłowe ładunki
danych.

Po aktualizacji serwera uruchom jednorazowo migrację bazy danych
(`python3 server/security_migration.py`), aby utworzyć kolumny sieciowe,
tabelę najnowszego stanu systemu, zapisane preferencje pulpitu i historię
zdarzeń. Zaktualizuj agenta na każdym kliencie, aby zaczął raportować nowe
metryki. Aby monitorować sam serwer LUMS, zarejestruj go jako klienta i
zainstaluj oraz skonfiguruj agenta telemetrii również na tym hoście.

## Bezpieczeństwo i prywatność

Punkt końcowy telemetrii wymaga uwierzytelnienia klienta za pomocą
skonfigurowanego tokenu klienta LUMS.

Agent wysyła żądania przez HTTPS podczas łączenia się ze zdalnym serwerem.
Zwykły HTTP jest dozwolony wyłącznie dla `localhost`, `127.0.0.1` i `::1`.
Połączenia ze zdalnym serwerem wymagają HTTPS. Można skonfigurować opcjonalny
plik CA do weryfikacji certyfikatu.

Agent nie umieszcza tokenu klienta w ładunku JSON ani w dzienniku. Usługa
systemd działa w ograniczonym środowisku i nie wymaga uprawnień roota do
zbierania opisanych metryk.

Telemetria zawiera metadane o zasobach systemowych i działaniach
operacyjnych, a nie aktualizacje pakietów ani dowolne wyniki poleceń. Adresy
interfejsów, serwery DNS, nazwy usług i kontenerów mogą ujawniać wrażliwe
informacje o infrastrukturze; dostęp do pulpitu i API jest chroniony
uprawnieniem `clients.view`.

## Przechowywanie danych

Podczas przetwarzania nowych zgłoszeń telemetrii serwer usuwa próbki starsze
niż siedem dni.

Uwierzytelniony punkt końcowy historii akceptuje zakres od 1 do 168 godzin.
Dostęp wymaga odpowiedniego uprawnienia do przeglądania klientów. Duże zestawy
wyników mogą zostać zredukowane do maksymalnie 1,000 próbek.

Pulpit `/health` udostępnia zakresy historii 1-godzinnej, 24-godzinnej i
7-dniowej oraz odświeża wyświetlane dane co pięć sekund. Pokazuje wykorzystanie
procesora, pamięci i dysku oraz zagregowaną historię sieci, a także bieżące
szczegóły dotyczące dysku, obciążenia, czasu działania, jądra, systemu
operacyjnego, interfejsów, łączności, czujników, usług i kontenerów wybranego
klienta. Wyświetla też przegląd floty (z filtrowaniem według stanu,
nieaktualnej telemetrii lub wysokiego obciążenia, wyszukiwaniem i
sortowaniem) oraz szczegóły poszczególnych klientów. Procesor i pamięć można
pokazać na wykresie liniowym, warstwowym lub pierścieniowym wskazującym
bieżącą wartość; wybrany widok jest zapamiętywany w przeglądarce. Ruch
sieciowy jest przedstawiany jako szybkość pobierania i wysyłania danych.
Telemetria starsza niż dwie minuty jest oznaczana jako nieaktualna. Przegląd
floty korzysta z punktu końcowego `/api/telemetry/overview`, który wymaga
uprawnienia do przeglądania klientów. Żądania historii są ograniczone do
zakresu 1–168 godzin i mogą zostać zredukowane do maksymalnie 1,000 próbek.
Timer systemd jest skonfigurowany tak, aby uruchamiać jednorazowego agenta co
pięć sekund; rzeczywista częstotliwość próbek zależy od czasu działania
usługi i dostępności sieci. Pulpit wyświetla również ostatnie nieudane
logowania SSH, liczbę ostrzeżeń i błędów dziennika oraz historię logowań,
wylogowań i uruchomień systemu. Ostrzeżenia progowe korzystają z zapisanych
limitów procesora, RAM-u i dysku zalogowanego użytkownika (domyślnie 90%).
Układ pulpitu jest stały; nie można go obecnie dostosowywać. Liczniki
dziennika obejmują najwyżej 500 pasujących wpisów na zapytanie. Informację o
ostatnim pomyślnym utworzeniu kopii zapasowej odczytuje się z dziennika
audytu serwera; nie jest to test odtworzenia kopii.

Przekroczenia progów i przerwy w telemetrii dłuższe niż dwie minuty są
widoczne w historii zdarzeń. Przekroczenia progów są wyliczane z zachowanych
próbek i korzystają z progów zapisanych dla zalogowanego użytkownika; zmiany
stanu usług i nowe znaczniki czasu nieudanych logowań SSH są rejestrowane
podczas przyjmowania danych. Zdarzenia są przechowywane przez maksymalnie
siedem dni, a punkt końcowy zdarzeń zwraca najwyżej 500 wpisów.

Dla wybranego klienta i zakresu czasu można eksportować dane w formacie CSV
i JSON. Pobrana historia zawiera wszystkie zachowane próbki z tego zakresu;
wykresy pozostają ograniczone do maksymalnie 1,000 punktów. Eksport wymaga
uprawnienia `clients.view` i nie jest buforowany przez przeglądarkę.

Jeśli skonfigurowano Wazuh i Suricata, wiersze ich stanu pokazują wyłącznie
stan odpowiedniej usługi systemd; LUMS nie łączy się z ich API ani nie zbiera
ich alertów. Aby raportować stan usługi, dodaj jej zainstalowaną jednostkę
(na przykład `wazuh-agent.service`, `wazuh-manager.service` lub
`suricata.service`) do listy dozwolonych `LUMS_MONITORED_SERVICES` agenta.
LUMS nie wymaga ani nie przechowuje poświadczeń do tych integracji.

## Konfiguracja

Agent telemetrii korzysta ze zmiennych środowiskowych `LUMS_BASE`,
`LUMS_TOKEN` i opcjonalnie `LUMS_CA_FILE`. Połączenia ze zdalnym serwerem
wymagają HTTPS. Instrukcje instalacji i konfiguracji znajdują się w
[przewodniku instalacji](../../../install.md).

## Instalacja i obsługa

Usługa telemetrii jest niezależna od zwykłego klienta LUMS. W systemie Debian
najpierw zaktualizuj kopię repozytorium LUMS na kliencie, a następnie uruchom
z jego katalogu głównego `sudo bash scripts/install-telemetry-agent.sh`.
Instalator sprawdza, czy `/etc/default/lums-agent` definiuje `LUMS_BASE` i
`LUMS_TOKEN`, instaluje aktualny kolektor i jednostki systemd, włącza timer
oraz wysyła próbkę testową. Nigdy nie wyświetla tokenu.

Sprawdź timer i usługę poleceniami `systemctl status
lums-telemetry.timer` oraz `systemctl status lums-telemetry.service`.
Przejrzyj najnowsze dzienniki usługi poleceniem
`journalctl -u lums-telemetry.service -n 30 --no-pager`. Nieaktywna usługa
jednorazowa między zaplanowanymi uruchomieniami nie musi oznaczać błędu;
sprawdź również timer i najnowsze dzienniki.

Strona `/monitoring` rozróżnia brak próbek, podstawową telemetrię bez
szczegółowych migawek oraz nieaktualną migawkę, a także pokazuje te kontrole po
stronie klienta. Podczas diagnozowania problemów nie wklejaj ani nie
udostępniaj tokenu.

## Rozwiązywanie problemów

- **Nie pojawiają się próbki:** sprawdź adres URL serwera, token klienta i
  uwierzytelnianie.
- **Błędy TLS:** sprawdź certyfikat serwera i skonfigurowany plik CA.
- **Błędy usługi:** sprawdź dziennik usługi.
- **Brak historii:** sprawdź uprawnienie do przeglądania klientów i żądany
  zakres czasu (1–168 godzin).

Informacje o progach stanu pulpitu i ograniczeniach wskaźnika miejsca na kopie
zapasowe znajdziesz w [dokumencie o pulpicie kondycji LUMS](panel-zdrowia-lums.md).
Ogólne wskazówki zawierają również [przewodnik instalacji](../../../install.md)
i [rozwiązywania problemów](../../../troubleshooting.md).

Źródła: [oryginał po angielsku](../../../telemetry.md).
