# Pulpit kondycji LUMS

## Cel i zakres

Uwierzytelniony pulpit pod adresem `/health` zapewnia operatorowi szybki
podgląd wybranych informacji o stanie LUMS i floty:

- stan bazy danych określony przez aplikację;
- łączną liczbę klientów oraz liczbę klientów online, o nieznanym stanie i
  offline;
- najnowsze dane telemetryczne o procesorze, pamięci i sieci dla włączonego
  klienta, jeśli telemetria jest zainstalowana i dostępne są próbki;
- historię alertów i wykryte przerwy w telemetrii;
- informację, czy można sprawdzić skonfigurowany katalog kopii zapasowych,
  najnowszy rozpoznany przez aplikację plik kopii oraz ostatnie pomyślne
  utworzenie kopii odnotowane w dzienniku audytu;
- opcjonalne wiersze stanu usług systemd Wazuh i Suricata, jeśli je
  skonfigurowano.

Szczegółowe odczyty hosta i sieci, temperatury, stany usług i kontenerów oraz
podsumowania zdarzeń bezpieczeństwa są dostępne na osobnej stronie
`/monitoring`. Jednostka telemetrii ma dostęp do dziennika systemowego
wyłącznie do odczytu na potrzeby podsumowań zdarzeń; nie wysyła surowych
komunikatów dziennika, nazw użytkowników ani adresów źródłowych. Szczegóły
kontenerów są niedostępne, chyba że konto usługi telemetrii może sprawdzać
środowisko uruchomieniowe bez dodatkowych uprawnień. Te strony nie
potwierdzają, że host, demon Docker, odwrotne proxy, sieć ani każdy zarządzany
klient działa prawidłowo. Widoczność kopii zapasowej nie dowodzi, że można ją
odtworzyć; okresowo wykonuj kontrolny test odtworzenia.

## Kontrola dostępu

Strona `/health` wymaga zalogowanego użytkownika z uprawnieniem
`clients.view`. Dostęp podlega standardowym mechanizmom uwierzytelniania i
autoryzacji aplikacji. Nie udostępniaj pulpitu publicznie przez pomijanie
logowania ani zabezpieczeń odwrotnego proxy.

Oddzielny punkt końcowy `GET /api/health` zwraca uproszczoną informację o
dostępności. Pomyślna odpowiedź oznacza, że trasa może odpowiedzieć; nie jest
pełną oceną stanu bazy danych, kopii zapasowych ani klientów.

## Interpretacja stanu klienta

Pulpit klasyfikuje klientów na podstawie czasu ich ostatniego zgłoszenia:

| Stan | Wiek znacznika czasu |
| --- | --- |
| Online | 120 sekund lub mniej |
| Nieznany | Ponad 120 sekund i do 600 sekund, brak/nieprawidłowy znacznik czasu albo znacznik czasu z przyszłości |
| Offline | Ponad 600 sekund |

Progi te opisują aktualność zgłoszeń, a nie to, czy komputer jest włączony
ani czy działają na nim wszystkie usługi. Na wynik mogą wpływać opóźnienia
sieci, uśpione komputery, zatrzymany agent lub błędy raportowania. Stan
`unknown` oznacza brak wystarczających informacji, a nie potwierdzoną awarię.

## Telemetria procesora i pamięci

Telemetria jest opcjonalna i niezależna od agenta raportującego oraz procesu
Watcher. Gdy timer systemd jest włączony, a klient może połączyć się z
serwerem, usługa telemetrii wysyła próbkę mniej więcej co pięć sekund.

Pulpit udostępnia zakresy historii 1-godzinnej, 24-godzinnej i 7-dniowej oraz
odświeża dane telemetryczne floty co pięć sekund. Szczegółowe dane hosta na
stronie `/monitoring` pochodzą z najnowszej zgłoszonej migawki; przepustowość
poszczególnych interfejsów oblicza się z kolejnych migawek. Zapytania o
historię są ograniczone do 1–168 godzin i mogą zostać zredukowane do
maksymalnie 1,000 punktów. Podczas przetwarzania nowych zgłoszeń telemetrii
próbki starsze niż siedem dni są usuwane; jeśli wszystkie zgłoszenia ustaną,
nie zakładaj, że czyszczenie danych odbywa się niezależnie.

Strona monitorowania ogranicza każde zapytanie do dziennika do 500 pasujących
wpisów; wyświetlona liczba `500+` oznacza, że wpisów może być więcej.
Historia logowań i wylogowań jest ograniczona do 20 zdarzeń, a historia
uruchomień systemu do 10 pozycji. Pulpit kondycji ma stały układ i korzysta z
istniejących progów procesora/RAM-u/dysku zapisanych dla użytkownika
(domyślnie 90%). Przekroczenia progów i przerwy w telemetrii są wyliczane z
zachowanej historii próbek; zmiany stanu usług i nowe zgłoszone nieudane
logowania SSH są zapisywane jako zdarzenia ze znacznikami czasu przez
maksymalnie siedem dni. Eksport CSV/JSON zawiera wszystkie próbki z wybranego
zakresu; interaktywne wykresy są ograniczone do 1,000 punktów.

Wiersze Wazuh i Suricata są opcjonalne i raportują wyłącznie stany usług
systemd. Wymagają dodania odpowiedniej zainstalowanej jednostki do
`LUMS_MONITORED_SERVICES`; nie łączą się z API Wazuh ani Suricata i nie
importują strumieni ich alertów. Znacznik czasu uruchomienia kopii pochodzi z
dziennika audytu i nie stanowi niezależnej weryfikacji możliwości jej
odtworzenia.

Telemetria wymaga uwierzytelnienia klienta. Połączenia zdalnego agenta
wymagają HTTPS; zwykły HTTP jest akceptowany tylko dla adresów loopback.
Skonfiguruj plik CA, jeśli serwer korzysta z prywatnego urzędu certyfikacji.
Szczegóły konfiguracji znajdziesz w
[przewodniku telemetrii](telemetria.md) i
[przewodniku instalacji](../../../install.md).

## Stan magazynu kopii zapasowych

Sekcja kopii zapasowych pokazuje informacje, które aplikacja może odczytać z
konfigurowanego katalogu kopii, oraz najnowszy rozpoznany plik kopii. Nie
weryfikuje niezależnie zawartości każdej kopii, nie potwierdza replikacji
poza hostem ani nie dowodzi, że odtworzenie bazy danych się powiedzie.

Zalecana rutyna operacyjna:

1. sprawdź, czy wyświetlana data kopii spełnia wymagania dotyczące
   dopuszczalnego czasu odtworzenia;
2. sprawdź zadanie tworzenia kopii i dzienniki aplikacji pod kątem błędów;
3. upewnij się, że kopia jest przenoszona do odpowiednio chronionej lokalizacji;
4. okresowo przetestuj odtworzenie w osobnej, kontrolowanej lokalizacji.

Nie usuwaj ani nie nadpisuj działającej bazy danych lub plików kopii zapasowych
w ramach doraźnego rozwiązywania problemów.

## Zalecane kontrole przy nieprawidłowym stanie

1. Sprawdź kontener LUMS i najnowsze dzienniki.
2. Jeśli strona lub API są niedostępne, sprawdź konfigurację odwrotnego proxy
   i TLS.
3. W przypadku klienta o stanie nieznanym lub offline sprawdź timery agenta
   raportującego i procesu Watcher oraz najnowsze wpisy dziennika.
4. Jeśli brakuje telemetrii, sprawdź `lums-telemetry.timer`,
   `lums-telemetry.service` oraz konfigurację klienta i serwera.
5. W przypadku ostrzeżeń dotyczących kopii sprawdź skonfigurowaną ścieżkę,
   uprawnienia systemu plików, dostępną przestrzeń i najnowsze dzienniki kopii.
6. Przed wprowadzaniem zmian zanotuj zaobserwowany stan i znaczniki czasu.

Zobacz [rozwiązywanie problemów](../../../troubleshooting.md), aby poznać
polecenia diagnostyczne, oraz
[administrację i kopie zapasowe](Administracja%20i%20kopie%20zapasowe.md), aby
zapoznać się z rutynową konserwacją i procedurami tworzenia kopii.

Źródło: [oryginał po angielsku](../../../LUMS_Health_Dashboard.md).
