# LUMS — Dokumentacja bezpieczeństwa

**LUMS — Linux Update Management Server**

Ten dokument opisuje obecną architekturę bezpieczeństwa, wdrożone mechanizmy bezpieczeństwa, wyniki audytu bezpieczeństwa, ograniczenia operacyjne oraz decyzje projektowe związane z bezpieczeństwem w LUMS.

Dokument odzwierciedla **obecnie wdrożony stan systemu**. Planowane lub przyszłe usprawnienia są wyraźnie oznaczone jako takie.

---

# Zasady bezpieczeństwa

LUMS stosuje podejście defense-in-depth w zarządzaniu aktualizacjami Linuksa.

Model bezpieczeństwa oddziela uwierzytelnianie administracyjne, uwierzytelnianie klientów, autoryzację, kontrolowane wykonywanie aktualizacji i logowanie audytowe.

Główne cele bezpieczeństwa to:

* uwierzytelniony dostęp administracyjny
* autoryzacja oparta na rolach
* uwierzytelniona komunikacja z klientami
* kontrolowane wykonywanie aktualizacji
* ochrona przed równoczesnym wykonywaniem zadań
* zadania aktualizacji możliwe do odzyskania
* chronione sekrety
* kontrolowane wykonywanie kontenera
* audytowalne operacje istotne dla bezpieczeństwa
* przewidywalna obsługa awarii
* testy regresji bezpieczeństwa

LUMS jest przeznaczony przede wszystkim do kontrolowanych środowisk infrastrukturalnych, laboratoryjnych i sieci wewnętrznych.

Nie należy go wystawiać bezpośrednio do publicznego Internetu bez dodatkowego przeglądu bezpieczeństwa i odpowiednich mechanizmów kontroli sieciowej.

---

# Architektura bezpieczeństwa

LUMS składa się z następujących komponentów istotnych dla bezpieczeństwa:

* interfejs administracyjny webowy
* REST API
* baza danych SQLite
* Agent LUMS na zarządzanych klientach
* backendy zarządzania pakietami APT i pacman
* mechanizmy zadań aktualizacji i odzyskiwania
* reverse proxy HTTPS Nginx
* utwardzony kontener Docker

Podstawowy przepływ zarządzania to:

Browser → HTTPS/Nginx → LUMS API → SQLite → LUMS Agent → Package Manager → Result → SQLite → Web UI

Uwierzytelnianie i autoryzacja są celowo oddzielone.

Ważna sesja uwierzytelniona nie przyznaje automatycznie dostępu do każdej operacji administracyjnej.

Autoryzacja jest egzekwowana po stronie serwera. Interfejs webowy dodatkowo ukrywa funkcje niedostępne dla bieżącej roli, ale widoczność w interfejsie nigdy nie jest traktowana jako granica bezpieczeństwa.

---

## Uwierzytelnianie administracyjne

Użytkownicy administracyjni uwierzytelniają się przez interfejs webowy LUMS.

Hasła nigdy nie są przechowywane w postaci jawnej. LUMS używa hashowania haseł opartego na Argon2 do przechowywania haseł.

Sesje administracyjne używają:

* uwierzytelnionej obsługi sesji po stronie serwera
* wygaśnięcia sesji
* regeneracji sesji
* ochrony CSRF dla żądań przeglądarki zmieniających stan
* ograniczania szybkości logowania
* unieważniania sesji podczas wylogowania
* walidacji roli po stronie serwera

Uwierzytelnianie i autoryzacja pozostają oddzielnymi mechanizmami bezpieczeństwa.

Pomyślnie uwierzytelniony użytkownik musi nadal posiadać wymagane uprawnienie
do operacji chronionych.

---

# Kontrola dostępu oparta na rolach

LUMS obecnie obsługuje trzy role użytkowników webowych:

* `administrator`
* `operator`
* `viewer`

Szablony ról są przechowywane w `users.role`; indywidualne uprawnienia są przechowywane
po stronie serwera w `user_permissions`.

Serwer ładuje skuteczne uprawnienia dla każdego uwierzytelnionego konta.
Informacje o uprawnieniach po stronie klienta kontrolują wyłącznie prezentację i nigdy
nie zastępują autoryzacji po stronie serwera.

## Administrator

Administratorzy mają pełny dostęp administracyjny i operacyjny.

Mogą:

* przeglądać klientów
* tworzyć klientów
* wyłączać klientów
* rotować tokeny klientów
* przeglądać zainstalowane pakiety i dostępne aktualizacje
* tworzyć zadania aktualizacji
* wykonywać obsługiwane operacje aktualizacji
* przeglądać historię zadań aktualizacji
* używać zarządzania pakietami
* używać funkcji konserwacji systemu
* zarządzać użytkownikami
* zarządzać rolami użytkowników
* uzyskiwać dostęp do funkcji administracyjnych

## Operator

Operatorzy mogą wykonywać operacyjne zadania zarządzania aktualizacjami.

Mogą:

* przeglądać klientów
* przeglądać zainstalowane pakiety i dostępne aktualizacje
* tworzyć zadania aktualizacji
* wykonywać obsługiwane operacje aktualizacji
* przeglądać historię zadań aktualizacji
* używać zarządzania pakietami
* używać funkcji konserwacji systemu

Operatorzy nie mogą:

* zarządzać użytkownikami
* zmieniać ról użytkowników
* tworzyć klientów
* wyłączać klientów
* rotować tokenów klientów

## Viewer

Viewerzy mają ograniczony dostęp tylko do odczytu.

Mogą:

* przeglądać klientów
* przeglądać zainstalowane oprogramowanie

Następujące obszary zarządzania są ukryte przed kontami Viewera:

* Aktualizacje
* Zadania aktualizacji
* Historia aktualizacji
* Zarządzanie pakietami
* Konserwacja systemu

Konta Viewera nie mogą wykonywać operacji zarządzania aktualizacjami zmieniających stan.

Serwer niezależnie egzekwuje te ograniczenia przez uwierzytelnianie
i kontrole uprawnień poszczególnych użytkowników.

---

# Uwierzytelnianie klientów

Każdy zarządzany klient LUMS używa indywidualnego tokena Bearer.

Mechanizm uwierzytelniania podlega modelowi:

`Authorization: Bearer <CLIENT_TOKEN>`

Serwer nie przechowuje tokenów klientów jako wartości jawnych.

Zamiast tego LUMS przechowuje szesnastkowy skrót SHA-256 tokena klienta.

Przepływ uwierzytelniania to:

Client Token → SHA-256 → Token Digest → SQLite

Uwierzytelnianie klienta weryfikuje uwierzytelniony token względem zarejestrowanego klienta i dodatkowo sprawdza odpowiedni stan klienta.

Model bezpieczeństwa nie używa adresu IP źródła jako jedynego dowodu tożsamości klienta.

Pozwala to LUMS działać w:

* prywatnych sieciach laboratoryjnych
* izolowanej infrastrukturze
* sieciach opartych na NAT
* środowiskach offline
* sieciach, w których adresy klientów mogą się zmieniać

Tokeny klientów mogą być rotowane przez upoważnionych administratorów.

Rotacja tokena generuje token zastępczy, przechowuje tylko jego skrót, unieważnia poprzedni token, zapisuje działanie administracyjne w logu audytowym i prezentuje token zastępczy jednorazowo.

Jawne wartości tokenów klientów nie są zapisywane w rekordach audytowych.

---

# Audyt bezpieczeństwa

Audyt bezpieczeństwa jest przeprowadzany przyrostowo.

Każdy obszar audytu jest weryfikowany względem rzeczywistej implementacji, a następnie przez testy automatyczne, izolowaną weryfikację lub weryfikację produkcyjną, gdy ma to zastosowanie.

Obecne obszary audytu:

| Audyt | Obszar                                   | Status                    |
| ----- | ---------------------------------------- | ------------------------- |
| #01   | Klucze obce SQLite                       | PASS                      |
| #02   | Konfiguracja runtime SQLite              | PASS                      |
| #03   | Obsługa limitów czasu aktualizacji       | PASS                      |
| #04   | Ograniczanie szybkości logowania         | PASS                      |
| #05   | Walidacja danych wejściowych API         | PASS                      |
| #06   | Unieważnianie sesji                      | PASS                      |
| #07   | Rotacja tokenów klientów                 | PASS                      |
| #08   | Obsługa adresów IP / sieci offline       | PASS                      |
| #09   | Odzyskiwanie zadań / punkty kontrolne    | PASS                      |
| #10   | Odporność APT                            | PASS                      |
| #11   | Wykrywanie ponownego uruchomienia Arch   | PASS                      |
| #12   | Testy jednostkowe / walidacja wyników API | PASS                     |
| #13   | Testy symulacyjne                        | PASS                      |
| #14   | Ciągła integracja                        | PASS                      |
| #15   | Logowanie aplikacji / audytu             | PASS                      |
| #16   | Wersjonowanie / wydania                  | Sprawdź [Releases](https://github.com/NovaForgeCtrl/LUMS/releases) i [tagi](https://github.com/NovaForgeCtrl/LUMS/tags) |
| #17   | Kontrola dostępu oparta na rolach        | PASS                      |

Tabela rejestruje zakres i wyniki wcześniejszych weryfikacji; nie jest certyfikacją ani gwarancją dla późniejszych rewizji. Odpowiednie kontrole należy ponownie wykonać na dokładnym kodzie przeznaczonym do wdrożenia. Dostępność wydań jest dynamiczna: sprawdź [Releases](https://github.com/NovaForgeCtrl/LUMS/releases) i [tagi](https://github.com/NovaForgeCtrl/LUMS/tags) repozytorium, zamiast wnioskować o stanie na podstawie tego dokumentu.

# Audyt bezpieczeństwa #01

## Klucze obce SQLite

Egzekwowanie kluczy obcych SQLite jest włączone dla połączeń z bazą danych aplikacji.

Aplikacja jawnie włącza:

`PRAGMA foreign_keys = ON`

Zapewnia to egzekwowanie integralności referencyjnej dla relacji między powiązanymi rekordami bazy danych.

Audyt zweryfikował:

* egzekwowanie kluczy obcych w runtime
* integralność kluczy obcych
* zachowanie cyklu życia klienta
* zachowanie wyłączania klienta
* zachowanie historycznych informacji o zadaniach
* zachowanie informacji audytowych

Stan klienta jest obsługiwany konserwatywnie.

W odpowiednich przypadkach klienci są wyłączani, a nie usuwani w sposób, który zniszczyłby historyczne informacje operacyjne.

**Status: PASS**

---

# Audyt bezpieczeństwa #02

## Konfiguracja runtime SQLite

Produkcyjna baza danych SQLite została przejrzana pod kątem konfiguracji runtime.

Zweryfikowana konfiguracja produkcyjna to:

* `journal_mode`: `wal`
* `busy_timeout`: `5000`
* `synchronous`: `2`

Aplikacja jawnie włącza:

`PRAGMA foreign_keys = ON`

Produkcyjna baza danych obecnie używa trybu WAL.

Konfiguracja bazy danych została udokumentowana na podstawie rzeczywistego zweryfikowanego stanu produkcyjnego, a nie historycznej konfiguracji rozwojowej.

Skonfigurowany limit czasu busy redukuje natychmiastowe awarie bazy danych, gdy inna transakcja tymczasowo trzyma bazę danych.

Ustawienie kluczy obcych na poziomie aplikacji zapewnia integralność referencyjną dla każdego połączenia z bazą danych.

Audyt obejmował weryfikację produkcyjną aktywnej konfiguracji SQLite.

**Status: PASS**

---

# Audyt bezpieczeństwa #03

## Limit czasu aktualizacji i obsługa procesów

Wykonywanie aktualizacji jest chronione przed procesami menedżera pakietów blokującymi się na czas nieokreślony.

Przepływ wykonania to:

Start process
↓
Read process output
↓
Monitor timeout
↓
Timeout reached?
↓
Terminate process
↓
Grace period
↓
Process still running?
↓
Kill process if required
↓
Complete job

Implementacja używa kontrolowanej obsługi podprocesów, aby ciche procesy nie mogły blokować się na czas nieokreślony podczas oczekiwania na dane wyjściowe.

Obsługa limitów czasu została przetestowana pod kątem:

* cichych procesów
* normalnego zakończenia procesu
* warunków przekroczenia limitu czasu
* procesów opierających się normalnemu zakończeniu
* awaryjnego zabijania
* zachowania limitu czasu na poziomie integracji

Mechanizm limitu czasu zapobiega pozostawaniu operacji zarządzania pakietami w stanie aktywnym przez czas nieokreślony.

Błędy i warunki przekroczenia limitu czasu są zwracane jako kontrolowane wyniki zadań i zapisywane w stanie zadania.

Obecna udokumentowana wersja Agenta LUMS to:

`1.7.0`

**Status: PASS**

---

# Audyt bezpieczeństwa #04

## Ograniczanie szybkości logowania

Próby logowania administracyjnego są ograniczane szybkościowo.

Obecna polityka eskalacji to:

* 5 nieudanych prób → 30 sekund
* 6 nieudanych prób → 60 sekund
* 7 nieudanych prób → 120 sekund
* 8 lub więcej nieudanych prób → 300 sekund

Stan ograniczania szybkości jest utrwalany w SQLite.

Równoczesne niepowodzenia logowania używają transakcyjnego blokowania bazy danych z:

`BEGIN IMMEDIATE`

Zapobiega to omijaniu zamierzonego stanu ograniczania szybkości przez równoczesne błędy uwierzytelniania w wyniku warunków wyścigu.

Pomyślne uwierzytelnienie czyści odpowiedni stan niepowodzenia.

Audyt obejmował:

* izolowane zachowanie ograniczania szybkości
* równoczesne niepowodzenia uwierzytelniania
* wycofywanie transakcji
* obsługę blokad bazy danych
* zachowanie resetowania po pomyślnym logowaniu
* zdarzenia audytowe ograniczania szybkości
* produkcyjne zachowanie logowania

Ogranicznik szybkości zapewnia więc mechanizm kontroli po stronie serwera przeciw powtarzającym się próbom uwierzytelniania, zamiast polegać na zachowaniu klienta.

**Status: PASS**

---

# Status audytu po części 2

Pierwsze cztery obszary audytu bezpieczeństwa są zakończone:

| Audyt | Obszar                            | Status |
| ----- | --------------------------------- | ------ |
| #01   | Klucze obce SQLite                | PASS   |
| #02   | Konfiguracja runtime SQLite       | PASS   |
| #03   | Limit czasu aktualizacji / obsługa procesów | PASS |
| #04   | Ograniczanie szybkości logowania  | PASS   |

Następujące obszary audytu są udokumentowane w kolejnych sekcjach:

* #05 Walidacja danych wejściowych API
* #06 Unieważnianie sesji
* #07 Rotacja tokenów klientów
* #08 Obsługa adresów IP / sieci offline
* #09 Odzyskiwanie zadań / punkty kontrolne
* #10 Odporność APT
* #11 Wykrywanie ponownego uruchomienia Arch
* #12 Testy jednostkowe / walidacja wyników API
* #13 Testy symulacyjne
* #14 Ciągła integracja
* #15 Logowanie aplikacji / audytu
* #16 Wersjonowanie / wydania
* #17 Kontrola dostępu oparta na rolach

# Audyt bezpieczeństwa #05

## Walidacja danych wejściowych API

LUMS waliduje wrażliwe pod względem bezpieczeństwa dane wejściowe API po stronie serwera.

Wartości dostarczane przez klienta nie są uznawane za zaufane tylko dlatego, że pochodzą z uwierzytelnionego interfejsu webowego lub zarejestrowanego klienta.

Walidacja jest stosowana do odpowiednich parametrów API, w tym:

* identyfikatorów klientów
* nazw pakietów
* działań zadań aktualizacji
* list pakietów
* parametrów wyszukiwania
* parametrów zarządzania użytkownikami
* operacji na tokenach klientów
* danych wyników zadań

Nazwy pakietów są walidowane przed przekazaniem ich do operacji zarządzania pakietami.

API zadań aktualizacji akceptuje tylko jawnie obsługiwane działania.

Obecnie obsługiwane działania związane z pakietami to:

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

Nieoczekiwane działania są odrzucane.

Listy pakietów są walidowane przed utworzeniem zadania.

Dla `UPDATE_PACKAGE` żądany pakiet musi również znajdować się w informacjach o dostępnych aktualizacjach klienta.

Zapytania do bazy danych używają parametryzowanego SQL, zamiast konstruowania instrukcji SQL z niezaufanych danych wejściowych.

Zapobiega to interpretowaniu wartości kontrolowanych przez użytkownika jako składni SQL.

Audyt obejmował testy negatywnych danych wejściowych i przypadki testowe ukierunkowane na wstrzykiwanie SQL.

Mechanizmy walidacji zostały również zweryfikowane przez automatyczny zestaw testów.

**Status: PASS**

---

# Audyt bezpieczeństwa #06

## Unieważnianie sesji

LUMS chroni uwierzytelnione sesje administracyjne przed dalszym użyciem po wylogowaniu.

Obsługa sesji obejmuje:

* uwierzytelnione sesje po stronie serwera
* wygaśnięcie sesji
* regenerację sesji
* unieważnianie przy wylogowaniu
* kontrole uwierzytelniania po stronie serwera
* walidację roli po stronie serwera

Wylogowanie unieważnia aktywną uwierzytelnioną sesję.

Chronione endpointy API wymagają uwierzytelnionej sesji i nie polegają na stanie po stronie klienta do określenia, czy użytkownik pozostaje uwierzytelniony.

Stan sesji jest więc oceniany przez serwer dla operacji chronionych.

Żądania przeglądarki zmieniające stan wymagają dodatkowo ochrony CSRF.

Audyt zweryfikował, że:

* uwierzytelniony dostęp działa normalnie
* chronione endpointy odrzucają nieuwierzytelnione żądania
* wylogowanie unieważnia aktywną sesję
* wcześniej uwierzytelniona sesja nie może kontynuować korzystania z chronionej funkcjonalności po unieważnieniu
* informacje o roli są oceniane po stronie serwera

**Status: PASS**

---

# Audyt bezpieczeństwa #07

## Rotacja tokenów klientów

Każdy zarządzany klient LUMS używa indywidualnego tokena uwierzytelniania.

Tokeny klientów nie są przechowywane jako wartości jawne.

Zamiast tego LUMS przechowuje szesnastkowy skrót SHA-256 tokena klienta.

Model uwierzytelniania to:

`Authorization: Bearer <CLIENT_TOKEN>`

Serwer hashuje dostarczony token i porównuje wynikowy skrót z zarejestrowanym skrótem tokena klienta.

Upoważnieni administratorzy mogą rotować token klienta.

Rotacja tokena wykonuje następujące operacje:

1. Wygeneruj token zastępczy.
2. Oblicz jego skrót SHA-256.
3. Zastąp przechowywany skrót tokena klienta.
4. Unieważnij poprzedni token.
5. Zapisz działanie administracyjne w logu audytowym.
6. Przedstaw token zastępczy administratorowi.

Poprzedni token nie może się uwierzytelnić po rotacji.

Jawne wartości tokenów nie są zapisywane w logach audytowych.

Audyt zweryfikował:

* pomyślne uwierzytelnianie tokenem
* przechowywanie skrótu tokena
* rotację tokena
* unieważnienie poprzedniego tokena
* uwierzytelnianie tokenem zastępczym
* wymagania autoryzacji dla rotacji tokena
* logowanie audytowe
* ochronę przed nieupoważnioną rotacją

Rotacja tokenów klientów jest ograniczona do administratorów.

Operatorzy i viewerzy nie mogą rotować tokenów klientów.

**Status: PASS**

---

# Audyt bezpieczeństwa #08

## Obsługa adresów IP i sieci offline

LUMS nie używa adresu IP źródła klienta jako jedynego dowodu tożsamości klienta.

Uwierzytelnianie klienta opiera się na zarejestrowanym tokenie klienta.

Ten projekt jest zamierzony, ponieważ zarządzani klienci mogą działać w środowiskach, w których ich adres sieciowy się zmienia.

Obsługiwane scenariusze wdrożenia obejmują:

* prywatne sieci laboratoryjne
* sieci oparte na NAT
* izolowaną infrastrukturę
* klientów z dynamicznym adresowaniem
* środowiska offline
* kontrolowane sieci wewnętrzne

Serwer oddziela więc:

**Lokalizację sieciową**

od:

**Tożsamości klienta**

Ważny token klienta identyfikuje zarejestrowanego klienta.

Adres sieciowy klienta może być nadal rejestrowany do celów operacyjnych i audytowych, ale nie jest traktowany jako poświadczenie uwierzytelniania.

Implementacja unika również założeń, że klient musi być osiągalny z ustalonego adresu.

Jest to szczególnie ważne dla środowisk laboratoryjnych i infrastruktury, w których topologia sieci może się zmieniać bez zmiany logicznej tożsamości zarządzanego systemu.

Audyt zweryfikował uwierzytelnianie klientów bez polegania na ustalonym adresie IP źródła.

**Status: PASS**

---

# Status audytu po części 3

Następujące obszary audytu bezpieczeństwa są zakończone:

| Audyt | Obszar                                   | Status |
| ----- | ---------------------------------------- | ------ |
| #01   | Klucze obce SQLite                       | PASS   |
| #02   | Konfiguracja runtime SQLite              | PASS   |
| #03   | Limit czasu aktualizacji / obsługa procesów | PASS |
| #04   | Ograniczanie szybkości logowania         | PASS   |
| #05   | Walidacja danych wejściowych API         | PASS   |
| #06   | Unieważnianie sesji                      | PASS   |
| #07   | Rotacja tokenów klientów                 | PASS   |
| #08   | Obsługa adresów IP / sieci offline       | PASS   |

Następna sekcja obejmuje:

* #09 Odzyskiwanie zadań / punkty kontrolne
* #10 Odporność APT
* #11 Wykrywanie ponownego uruchomienia Arch
* #12 Testy jednostkowe / walidacja wyników API

# Audyt bezpieczeństwa #09

## Odzyskiwanie zadań i punkty kontrolne

Zadania aktualizacji LUMS są zaprojektowane do bezpiecznego odzyskiwania po przerwanym wykonaniu.

Zadania aktualizacji utrzymują trwały stan w bazie danych SQLite.

Poszczególne operacje na pakietach są śledzone oddzielnie od ogólnego stanu zadania.

Pozwala to Agentowi ustalić, które operacje na pakietach zostały już pomyślnie ukończone, zanim przerwane zadanie zostanie wznowione.

Podczas odzyskiwania pomyślnie ukończone operacje na pakietach nie są wykonywane ponownie.

Logika odzyskiwania podlega więc zasadzie:

`Persistent Job State → Determine Completed Work → Skip Completed Items → Continue Remaining Work`

Zmniejsza to ryzyko niepotrzebnego powtarzania operacji na pakietach po:

* przerwaniu Agenta
* zakończeniu procesu
* ponownym uruchomieniu systemu
* tymczasowej awarii komunikacji
* ponownym uruchomieniu kontenera
* innych przerwach wykonania

Audyt zweryfikował odzyskiwanie przerwanych zadań i zachowanie punktów kontrolnych.

Odzyskiwanie zostało przetestowane z zadaniami zawierającymi wiele operacji na pakietach oraz z wcześniej pomyślnymi elementami pakietów.

Audyt potwierdził, że ukończona praca jest zachowywana, a pozostała praca może być kontynuowana bez niepotrzebnego powtarzania pomyślnych operacji.

**Status: PASS**

---

# Audyt bezpieczeństwa #10

## Odporność APT

Operacje na pakietach w systemach opartych na Debianie są wykonywane przez warstwę zarządzania pakietami LUMS.

Operacje aktualizacji związane z APT zostały przejrzane pod kątem niezawodnego wykrywania stanu menedżera pakietów i wyników aktualizacji.

Implementacja uwzględnia przypadki, w których polecenia zarządzania pakietami mogą zwracać sukces, wymagając jednocześnie dodatkowej interpretacji ich danych wyjściowych lub wynikowego stanu systemu.

Wykrywanie aktualizacji APT zostało utwardzone, aby uniknąć polegania na jednym uproszczonym warunku danych wyjściowych polecenia.

Audyt obejmował testowanie:

* normalnych operacji APT
* dostępnych aktualizacji pakietów
* instalacji pakietów
* usuwania pakietów
* wykonywania zadań aktualizacji
* obsługi wyników APT
* zachowania wykrywania aktualizacji

Odpowiednie utwardzenie zostało zatwierdzone jako:

`c76f331 security: harden apt update detection`

Celem jest zapewnienie, że LUMS nie zgłasza niepoprawnie stanu zarządzania pakietami wyłącznie na podstawie niekompletnych lub niejednoznacznych danych wyjściowych polecenia.

**Status: PASS**

---

# Audyt bezpieczeństwa #11

## Wykrywanie ponownego uruchomienia Arch Linux

Operacje na pakietach w Arch Linux mogą skutkować stanem systemu, w którym wymagane lub zalecane jest ponowne uruchomienie.

LUMS ocenia więc wynikowy stan systemu po odpowiednich operacjach zarządzania pakietami.

Agent rozróżnia normalne zakończenie operacji na pakiecie od sytuacji, w której wymagane jest ponowne uruchomienie.

Stan ponownego uruchomienia jest raportowany z powrotem do serwera LUMS jako część wyniku zadania.

Pozwala to interfejsowi zarządzania rozróżnić:

* pomyślną operację na pakiecie
* pomyślną operację z wymaganiem ponownego uruchomienia
* nieudaną operację

Audyt zweryfikował wykrywanie ponownego uruchomienia Arch Linux przy użyciu rzeczywistej ścieżki wykonywania zarządzania pakietami.

Implementacja została przetestowana pod kątem warunków wymagających ponownego uruchomienia i normalnych warunków zakończenia.

**Status: PASS**

---

# Audyt bezpieczeństwa #12

## Testy jednostkowe i walidacja wyników API

Zachowanie wrażliwe pod względem bezpieczeństwa jest objęte testami automatycznymi.

Zestaw testów obejmuje pokrycie uwierzytelniania, autoryzacji, walidacji API, zadań aktualizacji, zarządzania pakietami, uwierzytelniania klientów i obsługi wyników.

Ścieżka wyników Agent–serwer została specjalnie przejrzana, aby zapewnić, że wyniki zadań nie mogą arbitralnie zmieniać niepowiązanego stanu po stronie serwera.

Przetwarzanie wyników waliduje przesłane informacje przed zastosowaniem zmian stanu do odpowiedniego zadania aktualizacji.

Walidacja obejmuje odpowiednie pola wyników i oczekiwane relacje zadań.

Zapobiega to temu, by uwierzytelniony klient mógł swobodnie wybierać niepowiązane zadania lub wstrzykiwać arbitralny stan do bazy danych zadań aktualizacji.

Zestaw testów bezpieczeństwa obejmuje również przypadki negatywne i nieupoważnione.

Uruchom pełny automatyczny zestaw testów z katalogu głównego repozytorium za pomocą
`./.venv-test/bin/pytest -q`. Liczba testów zmienia się w czasie; używaj
wyniku bieżącego uruchomienia, a nie stałej liczby w tym dokumencie.

Odpowiednie mechanizmy bezpieczeństwa zostały dodatkowo zweryfikowane przez ukierunkowane uruchomienia testów podczas audytu.

**Status: PASS**

---

# Status audytu po części 4

Następujące obszary audytu bezpieczeństwa są zakończone:

| Audyt | Obszar                                   | Status |
| ----- | ---------------------------------------- | ------ |
| #01   | Klucze obce SQLite                       | PASS   |
| #02   | Konfiguracja runtime SQLite              | PASS   |
| #03   | Limit czasu aktualizacji / obsługa procesów | PASS |
| #04   | Ograniczanie szybkości logowania         | PASS   |
| #05   | Walidacja danych wejściowych API         | PASS   |
| #06   | Unieważnianie sesji                      | PASS   |
| #07   | Rotacja tokenów klientów                 | PASS   |
| #08   | Obsługa adresów IP / sieci offline       | PASS   |
| #09   | Odzyskiwanie zadań / punkty kontrolne    | PASS   |
| #10   | Odporność APT                            | PASS   |
| #11   | Wykrywanie ponownego uruchomienia Arch   | PASS   |
| #12   | Testy jednostkowe / walidacja wyników API | PASS  |

Następna sekcja obejmuje:

* #13 Testy symulacyjne
* #14 Ciągła integracja
* #15 Logowanie aplikacji / audytu
* #16 Wersjonowanie / wydania

# Audyt bezpieczeństwa #13

## Testy symulacyjne

LUMS zapewnia mechanizm symulacji do testowania przepływów zarządzania aktualizacjami bez wykonywania odpowiedniej operacji zarządzania pakietami na zarządzanym systemie.

Symulacja jest implementowana na warstwie wykonania Agenta.

Gdy symulacja jest włączona, operacje zarządzania pakietami są reprezentowane i przetwarzane bez zastosowania żądanej zmiany pakietu do systemu operacyjnego.

Pozwala to testować zachowanie zadań aktualizacji bez celowej modyfikacji zarządzanego systemu.

Testy symulacyjne obejmują odpowiednie ścieżki zarządzania aktualizacjami, w tym:

* instalację pakietów
* usuwanie pakietów
* aktualizacje pakietów
* aktualizacje systemu
* wykonywanie zadań
* raportowanie wyników
* pomyślne zakończenie
* obsługę awarii

Mechanizm symulacji został użyty podczas audytu bezpieczeństwa do weryfikacji tworzenia zadań, wykonywania przez Agenta, obsługi wyników i przejść stanu po stronie serwera niezależnie od rzeczywistych modyfikacji pakietów.

Tryb symulacji jest mechanizmem testowym i nie zastępuje mechanizmów autoryzacji normalnych operacji aktualizacji.

**Status: PASS**

---

# Audyt bezpieczeństwa #14

## Ciągła integracja

LUMS używa testów automatycznych do wykrywania regresji bezpieczeństwa i funkcjonalnych, zanim zmiany zostaną uznane za zakończone.

Proces CI uruchamia automatyczny zestaw testów względem projektu.

Środowisko testowe weryfikuje aplikację i funkcjonalność wrażliwą pod względem bezpieczeństwa niezależnie od produkcyjnego kontenera.

Proces CI obejmuje walidację:

* uwierzytelniania
* autoryzacji
* RBAC
* zachowania API
* obsługi zadań aktualizacji
* zachowania zarządzania pakietami
* uwierzytelniania klientów
* walidacji wyników zadań
* obsługi błędów wrażliwych pod względem bezpieczeństwa

Audyt CI został przejrzany po zmianach utwardzających bezpieczeństwo.

Końcowy zweryfikowany zestaw testów zakończył się pomyślnie.

Liczba testów zmienia się w miarę rozwoju projektu. CI zapewnia automatyczną
barierę regresji dla zmian aplikacji istotnych dla bezpieczeństwa.

**Status: PASS**

---

# Audyt bezpieczeństwa #15

## Logowanie aplikacji i audytu

LUMS rejestruje wrażliwe pod względem bezpieczeństwa zdarzenia administracyjne i operacyjne przez logowanie audytowe na poziomie aplikacji.

Logowanie audytowe jest zaprojektowane do zapewniania historii operacyjnej bez przechowywania wrażliwych poświadczeń.

Odpowiednie działania wrażliwe pod względem bezpieczeństwa obejmują zdarzenia takie jak:

* zdarzenia bezpieczeństwa związane z uwierzytelnianiem
* działania administracyjne
* zarządzanie klientami
* operacje na tokenach klientów
* tworzenie zadań aktualizacji
* wykonywanie zadań aktualizacji
* awarie istotne dla bezpieczeństwa

Wrażliwy materiał poświadczeń jest wykluczony z rekordów audytowych.

W szczególności:

* hasła nie są logowane
* jawne tokeny klientów nie są logowane
* wartości sekretów nie są celowo zapisywane w rekordach audytowych

Rekordy audytowe są powiązane z odpowiednim kontekstem administracyjnym lub operacyjnym, gdy ma to zastosowanie.

Implementacja logowania audytowego została przejrzana pod kątem:

* pokrycia zdarzeń wrażliwych pod względem bezpieczeństwa
* wykluczenia poświadczeń
* identyfikowalności administracyjnej
* obsługi awarii
* trwałości odpowiednich informacji audytowych

System logowania ma wspierać zarówno operacyjne rozwiązywanie problemów, jak i dochodzenia bezpieczeństwa.

**Status: PASS**

---

# Audyt bezpieczeństwa #16

## Wersjonowanie i wydania

Wersjonowanie i zarządzanie wydaniami są częścią przeglądu bezpieczeństwa, ponieważ operatorzy muszą móc zidentyfikować dokładny wdrażany kod i artefakty. Dostępność wydań i wersje komponentów zmieniają się niezależnie od tego przewodnika. Sprawdź aktualne [tagi](https://github.com/NovaForgeCtrl/LUMS/tags) i stronę [Releases](https://github.com/NovaForgeCtrl/LUMS/releases) repozytorium oraz metadane wersji w dokładnej rewizji wdrażanego kodu źródłowego. Nie traktuj tego dokumentu jako aktualnego katalogu wydań.

Obecne wersje komponentów obejmują:

* LUMS Agent: `1.7.0`
* LUMS Watcher: `1.2.1`

Planowany proces wydania to:

1. Zakończyć pracę implementacyjną.
2. Zakończyć przegląd bezpieczeństwa.
3. Przejrzeć i zsynchronizować dokumentację.
4. Zakończyć pełny automatyczny zestaw testów.
5. Zweryfikować CI.
6. Zdefiniować wersję wydania.
7. Utworzyć odpowiedni tag Git.
8. Opublikować GitHub Release.
9. Zachować wydanie jako udokumentowaną podstawę.

Wydanie należy opublikować dopiero po ukończeniu implementacji, przeglądu bezpieczeństwa, dokumentacji i testów regresji dla danej rewizji.

---

# Status audytu po części 5

Następujące obszary audytu bezpieczeństwa są zakończone:

| Audyt | Obszar                                   | Status                    |
| ----- | ---------------------------------------- | ------------------------- |
| #01   | Klucze obce SQLite                       | PASS                      |
| #02   | Konfiguracja runtime SQLite              | PASS                      |
| #03   | Limit czasu aktualizacji / obsługa procesów | PASS                   |
| #04   | Ograniczanie szybkości logowania         | PASS                      |
| #05   | Walidacja danych wejściowych API         | PASS                      |
| #06   | Unieważnianie sesji                      | PASS                      |
| #07   | Rotacja tokenów klientów                 | PASS                      |
| #08   | Obsługa adresów IP / sieci offline       | PASS                      |
| #09   | Odzyskiwanie zadań / punkty kontrolne    | PASS                      |
| #10   | Odporność APT                            | PASS                      |
| #11   | Wykrywanie ponownego uruchomienia Arch   | PASS                      |
| #12   | Testy jednostkowe / walidacja wyników API | PASS                     |
| #13   | Testy symulacyjne                        | PASS                      |
| #14   | Ciągła integracja                        | PASS                      |
| #15   | Logowanie aplikacji / audytu             | PASS                      |
| #16   | Wersjonowanie / wydania                  | Sprawdź [Releases](https://github.com/NovaForgeCtrl/LUMS/releases) i [tagi](https://github.com/NovaForgeCtrl/LUMS/tags) |

Pozostały numerowany techniczny obszar audytu to:

* #17 Kontrola dostępu oparta na rolach

# Audyt bezpieczeństwa #17

## Kontrola dostępu oparta na rolach

LUMS łączy szablony ról z indywidualnie przypisanymi uprawnieniami. Obsługiwane
szablony to `administrator`, `operator` i `viewer`; wybór szablonu wybiera jego
domyślne uprawnienia, które administrator może dostosować dla każdego konta.

Rola pozostaje metadanymi konta. Chronione trasy autoryzują względem
zestawu uprawnień przechowywanego po stronie serwera, a nie etykiety roli. Interfejs ukrywa
niedostępne funkcje dla wygody użytkownika, podczas gdy serwer pozostaje granicą bezpieczeństwa.

---

## Model uprawnień RBAC

| Uprawnienie       | Przyznawany dostęp |
| ----------------- | ------------------ |
| `clients.view`    | Przeglądanie klientów i informacji o systemie |
| `software.view`   | Przeglądanie zainstalowanego oprogramowania |
| `updates.view`    | Przeglądanie dostępnych aktualizacji, zadań i historii |
| `packages.search` | Wyszukiwanie w repozytoriach pakietów |
| `jobs.manage`     | Tworzenie operacji na pakietach i zadań aktualizacji |
| `clients.manage`  | Rejestrowanie/usuwanie klientów i rotacja tokenów klientów |
| `users.manage`    | Tworzenie użytkowników i zarządzanie rolami oraz uprawnieniami |

Domyślne szablony ról to:

| Szablon          | Domyślne uprawnienia |
| ---------------- | -------------------- |
| `administrator`  | Wszystkie uprawnienia |
| `operator`       | Widoczność klientów/oprogramowania/aktualizacji, wyszukiwanie pakietów i zarządzanie zadaniami |
| `viewer`         | Widoczność klientów i widoczność zainstalowanego oprogramowania |

Uprawnienia związane z klientami wymagają `clients.view`. `jobs.manage` wymaga również
`updates.view`. Interfejs użytkownika ładuje uprawnienia dla uwierzytelnionego konta i
pomija kontrolki, których użytkownik nie może używać; kontrole po stronie serwera niezależnie egzekwują
te same nadania.

---

## Egzekwowanie autoryzacji

Chronione operacje używają uwierzytelniania po stronie serwera i kontroli uprawnień.

Model autoryzacji podlega zasadzie:

`Authenticate → Load User Permissions → Authorize Operation → Execute`

Samo uwierzytelnienie nie wystarcza do uzyskania dostępu do operacji uprzywilejowanych.

Operacje zmieniające stan wymagają dodatkowo ochrony CSRF, gdy ma to zastosowanie.

Przykłady chronionych operacji administracyjnych obejmują:

* tworzenie zadań aktualizacji
* instalację pakietów
* usuwanie pakietów
* aktualizacje pakietów
* aktualizacje systemu
* operacje zarządzania pakietami
* tworzenie klientów
* wyłączanie klientów
* rotację tokenów klientów
* tworzenie użytkowników
* funkcje zarządzania użytkownikami

Chronione endpointy jawnie definiują uprawnienie wymagane dla
odpowiedniej operacji.

Brakujące uprawnienie jest odrzucane przez serwer, nawet jeśli użytkownik ręcznie
konstruuje odpowiednie żądanie HTTP.

Zapobiega to omijaniu modelu RBAC przez bezpośrednie wywołanie endpointu API, który jest ukryty w interfejsie webowym.

---

## Ograniczenia Viewera

Szablon Viewera jest celowo ograniczony przez swój domyślny zestaw uprawnień.

Dla kont bez odpowiednich nadań interfejs klienta nie udostępnia:

* Aktualizacji
* Zadań aktualizacji
* Historii aktualizacji
* Zarządzania pakietami
* Konserwacji systemu

Serwer dodatkowo uniemożliwia kontom bez odpowiednich nadań
wykonywanie chronionych operacji.

Interfejs JavaScript nie ładuje danych zarządzania aktualizacjami bez
`updates.view`.

Zmniejsza to niepotrzebną ekspozycję informacji operacyjnych, zachowując autoryzację po stronie serwera jako rzeczywistą kontrolę bezpieczeństwa.

Zainstalowane oprogramowanie pozostaje dostępne dla kont Viewera jako funkcja informacyjna tylko do odczytu.

---

## Administracyjne zarządzanie użytkownikami

Zarządzanie użytkownikami wymaga uprawnienia `users.manage`.

Użytkownicy z tym uprawnieniem mogą tworzyć konta bez uprawnień, a następnie
przypisywać indywidualne nadania lub zastosować szablon roli w edytorze uprawnień.
Szablony ról mają opisy wyjaśniające ich domyślne nadania.

Upoważnieni menedżerowie użytkowników mogą zapisać notatkę wewnętrzną dla każdego konta. Notatki są
ograniczone do 2000 znaków, nie są uwzględniane w szczegółach logu audytowego i nie
są widoczne dla właściciela konta.

Tworzenie użytkownika obejmuje:

* walidację nazwy użytkownika
* walidację roli
* walidację hasła
* hashowanie hasła Argon2
* wykrywanie duplikatów użytkowników
* logowanie audytowe
* ochronę CSRF
* autoryzację po stronie serwera

Endpointy zarządzania użytkownikami nie są dostępne bez `users.manage`.

Serwer odrzuca nieznane uprawnienia i nieprawidłowe kombinacje zależności.
Co najmniej jedno aktywne konto musi zachować `users.manage`; zmiany, które
usunęłyby ostatniego menedżera użytkowników, są odrzucane.

Hasła nigdy nie są przechowywane w postaci jawnej.

---

## Migracja bazy danych RBAC

Informacje o szablonie roli pozostają w rekordzie bazy danych użytkownika. Indywidualne
nadania są przechowywane w tabeli `user_permissions` z kluczem obcym do
konta użytkownika. Migracja `003-user-permissions` tworzy tę tabelę i wypełnia
istniejące konta na podstawie ich bieżącego szablonu roli, zachowując ich dostęp
podczas przejścia. Migracja `004-user-admin-notes` dodaje prywatne
pole `users.admin_note`; istniejące konta otrzymują pustą notatkę. Migracja
`005-backup-permission` przyznaje `backups.manage` istniejącym kontom Administratora.

Tworzenie kopii zapasowej bazy danych wymaga `backups.manage`; szablon Administratora
domyślnie zawiera to uprawnienie. Serwer zapisuje kopie zapasowe online SQLite tylko
do skonfigurowanego po stronie serwera `LUMS_BACKUP_DIR`; nie akceptuje
ścieżek systemu plików z przeglądarki. Pliki kopii zapasowych są tworzone z uprawnieniami tylko dla właściciela i są
sprawdzane pod kątem integralności przed publikacją.

---

## Testy bezpieczeństwa RBAC

Zachowanie RBAC jest objęte testami automatycznymi.

Testy obejmują:

* autoryzację Administratora
* autoryzację Operatora
* ograniczenia Viewera
* dostęp do chronionego API
* nieupoważnione operacje
* ograniczenia zarządzania klientami
* ograniczenia zadań aktualizacji
* ograniczenia zarządzania użytkownikami
* widoczność strony klienta
* zachowanie interfejsu specyficzne dla uprawnień

Testy RBAC obejmują domyślne ustawienia szablonów ról, niestandardowe uprawnienia, zależności
uprawnień i autoryzację po stronie serwera. Weryfikacja produkcyjna powinna
obejmować konta z niestandardowymi uprawnieniami, a także domyślne
szablony Administratora, Operatora i Viewera.

---

## Wynik bezpieczeństwa RBAC

Implementacja RBAC zapewnia warstwową autoryzację:

1. Uwierzytelnianie ustala tożsamość użytkownika.
2. Serwer ładuje uprawnienia użytkownika.
3. Chronione trasy egzekwują wymagane uprawnienie.
4. Ochrona CSRF ma zastosowanie do odpowiednich zmian stanu w przeglądarce.
5. Interfejs webowy ukrywa niedostępną funkcjonalność.
6. Testy automatyczne weryfikują granice autoryzacji.

Interfejs nie zapewnia więc sam mechanizmu autoryzacji.

Serwer pozostaje autorytatywną granicą bezpieczeństwa.

**Status: PASS**

# Zasady przeglądu dokumentacji

## Przegląd dokumentacji

Dokumentacja bezpieczeństwa jest przeglądana względem obecnie wdrożonego systemu LUMS.

Celem tego przeglądu jest zapewnienie, że dokumentacja bezpieczeństwa opisuje rzeczywistą implementację, a nie wcześniejszy stan rozwojowy.

Przegląd obejmuje:

* uwierzytelnianie
* autoryzację
* RBAC
* uwierzytelnianie klientów
* obsługę tokenów
* obsługę sesji
* ochronę CSRF
* ograniczanie szybkości
* konfigurację SQLite
* wykonywanie aktualizacji
* odzyskiwanie zadań
* zarządzanie pakietami
* utwardzanie kontenera
* ekspozycję sieciową
* obsługę sekretów
* bezpieczeństwo zależności i kompilacji
* uprawnienia systemu plików
* logowanie aplikacji i audytu
* wersjonowanie i obsługę wydań
* automatyczne testy bezpieczeństwa

Dokumentacja musi rozróżniać:

* wdrożone mechanizmy
* zweryfikowane zachowanie produkcyjne
* planowane usprawnienia
* celowo otwarte decyzje projektowe

Historyczne szczegóły implementacji nie mogą być prezentowane jako bieżąca konfiguracja produkcyjna.

W szczególności dokumentacja odzwierciedla bieżącą produkcyjną konfigurację SQLite, a nie bieżącą konfigurację WAL.

Bieżący produkcyjny runtime jest udokumentowany jako:

* `journal_mode = wal`
* `busy_timeout = 5000`
* `synchronous = 2`
* `PRAGMA foreign_keys = ON` na poziomie aplikacji

Bieżące zachowanie Viewer-RBAC jest również udokumentowane zgodnie z wdrożonym interfejsem produkcyjnym.

Użytkownicy Viewera mają dostęp do:

* informacji o klientach
* zainstalowanego oprogramowania

Użytkownicy Viewera nie mają dostępu do:

* Aktualizacji
* Zadań aktualizacji
* Historii aktualizacji
* Zarządzania pakietami
* Konserwacji systemu

Przegląd dokumentacji usuwa lub zastępuje również nieaktualne odniesienia do wcześniejszych liczby testów, stanów migracji, konfiguracji wdrożeń i zachowań wyłącznie rozwojowych.

Ten przewodnik należy weryfikować względem odpowiedniej implementacji po każdej zmianie funkcji lub mechanizmów bezpieczeństwa. Historycznych twierdzeń nie należy przedstawiać jako aktualnego stanu bez ich sprawdzenia.

---

# Dodatkowe utwardzanie bezpieczeństwa

Numerowany audyt bezpieczeństwa obejmuje podstawowe mechanizmy bezpieczeństwa aplikacji.

Dodatkowe utwardzanie zostało wykonane po pierwotnej sekwencji audytu i jest częścią bieżącej podstawy bezpieczeństwa.

Mechanizmy te są tutaj udokumentowane, ponieważ reprezentują ważne właściwości bezpieczeństwa bieżącego wdrożenia.

---

## Utwardzanie kontenera

Produkcyjny kontener LUMS działa z utwardzoną konfiguracją Docker.

Produkcyjny kontener używa:

* użytkownika aplikacji innego niż root
* systemu plików głównych tylko do odczytu
* usuniętych zdolności Linux
* `no-new-privileges`
* ograniczonych tymczasowych systemów plików
* sekretu montowanego tylko do odczytu
* dedykowanego trwałego wolumenu danych aplikacji
* polityki restartu
* publikacji portu aplikacji tylko na loopback

System plików głównych aplikacji nie jest więc zapisywalny podczas normalnego działania.

Zapisywalne lokalizacje są wyraźnie ograniczone do lokalizacji wymaganych przez aplikację.

Produkcyjny kontener został niezależnie sprawdzony w celu weryfikacji skutecznej konfiguracji runtime.

Utwardzony runtime został również przetestowany przez weryfikację, że:

* zapisy do systemu plików aplikacji zawodzą
* `/tmp` pozostaje dostępny, gdy jest wymagany
* `/var/lib/lums` pozostaje zapisywalny
* plik sekretu pozostaje tylko do odczytu
* aplikacja pozostaje operacyjna

---

## Ekspozycja sieciowa

Port aplikacji LUMS nie jest bezpośrednio wystawiony do LAN.

Port aplikacji Docker jest powiązany z interfejsem loopback:

`127.0.0.1:5050`

Dostęp zewnętrzny jest zapewniany przez Nginx.

Host produkcyjny wystawia zamierzone usługi sieciowe przez firewall i reverse proxy.

Zweryfikowano, że wdrożenie zapobiega bezpośredniemu zdalnemu dostępowi do wewnętrznego portu aplikacji Docker.

Firewall używa modelu domyślnego odrzucania dla ruchu przychodzącego i routowanego.

Zamierzone usługi osiągalne z zewnątrz to:

* SSH
* HTTP
* HTTPS

Żądania HTTP są przekierowywane do HTTPS przez serwer webowy.

Domyślna witryna Nginx została usunięta, aby niepowiązana domyślna zawartość nie była wystawiona.

---

## Bezpieczeństwo transportu

Dostęp administracyjny webowy jest zapewniany przez HTTPS.

HTTP jest przekierowywany do HTTPS.

Endpoint TLS jest obsługiwany przez Nginx, a nie bezpośrednio przez aplikację Flask/Gunicorn.

Utrzymuje to oddzielenie bezpieczeństwa transportu od serwowania aplikacji.

Wewnętrzny port aplikacji Gunicorn nie jest więc przeznaczony do bycia publicznym endpointem HTTP.

Bieżące wdrożenie jest przeznaczone dla kontrolowanej infrastruktury wewnętrznej.

Przyszłe wdrożenie z bezpośrednią ekspozycją do publicznego Internetu wymagałoby dodatkowego przeglądu bezpieczeństwa.

---

## Sekrety i konfiguracja

Sekrety produkcyjne nie są przechowywane w drzewie źródłowym aplikacji.

Klucz sekretu LUMS jest dostarczany przez chroniony plik sekretu.

Produkcyjny kontener otrzymuje sekret przez:

`/run/secrets/lums_secret`

Plik sekretu jest montowany tylko do odczytu.

Aplikacja odczytuje sekret przez skonfigurowany mechanizm pliku sekretu.

Obsługa repozytorium i kontekstu kompilacji Docker została przejrzana, aby zapobiec przypadkowemu włączeniu:

* plików bazy danych
* plików kopii zapasowych
* plików sekretów
* kluczy prywatnych
* certyfikatów
* logów runtime
* lokalnych artefaktów kopii zapasowych

Repozytorium ignoruje również typowe tymczasowe wzorce kopii zapasowych używane podczas developmentu.

---

## Bezpieczeństwo zależności i kompilacji

Produkcyjny obraz Docker używa przypiętego skrótu obrazu bazowego Python.

Zależności runtime produkcji są jawnie przypięte do wersji.

Obecny produkcyjny zestaw zależności obejmuje:

* Flask `3.1.3`
* argon2-cffi `25.1.0`
* Gunicorn `23.0.0`

Kontekst kompilacji Docker jest ograniczony przez `.dockerignore`.

Powtarzane kompilacje produkcyjne zostały porównane podczas audytu.

Odpowiednie metadane zależności i pakietów pozostały spójne między powtarzanymi kompilacjami, z wyjątkiem oczekiwanych różnic w generowanym bajtkodzie Pythona.

Zapewnia to powtarzalną podstawę dla produkcyjnego obrazu przy jednoczesnym ograniczeniu kontekstu kompilacji.

---

## Uprawnienia systemu plików i runtime

Aplikacja produkcyjna działa jako dedykowany użytkownik `lums`, a nie root.

Trwałe dane aplikacji są przechowywane w dedykowanym wolumenie danych LUMS.

System plików głównych aplikacji jest tylko do odczytu.

Dostęp do zapisu w runtime jest ograniczony do jawnie wymaganych lokalizacji.

Zweryfikowano, że produkcyjny runtime odrzuca nieupoważnione zapisy do systemu plików aplikacji.

Zmniejsza to wpływ przypadkowej lub złośliwej modyfikacji plików wewnątrz kontenera aplikacji.

---

# Wnioski z audytu bezpieczeństwa

Obecna implementacja LUMS przeszła szeroki przegląd bezpieczeństwa obejmujący:

* uwierzytelnianie
* autoryzację
* RBAC
* bezpieczeństwo sesji
* ochronę CSRF
* ograniczanie szybkości logowania
* bezpieczeństwo tokenów klientów
* walidację API
* odporność na wstrzykiwanie SQL
* integralność SQLite
* wykonywanie aktualizacji
* obsługę limitów czasu
* odzyskiwanie zadań
* odporność zarządzania pakietami
* walidację wyników
* symulację
* ciągłą integrację
* logowanie audytowe
* utwardzanie kontenera
* ekspozycję sieciową
* bezpieczeństwo transportu
* obsługę sekretów
* uprawnienia systemu plików
* bezpieczeństwo zależności i kompilacji

Numerowane wyniki audytu to:

| Audyt | Obszar                                   | Status                    |
| ----- | ---------------------------------------- | ------------------------- |
| #01   | Klucze obce SQLite                       | PASS                      |
| #02   | Konfiguracja runtime SQLite              | PASS                      |
| #03   | Limit czasu aktualizacji / obsługa procesów | PASS                   |
| #04   | Ograniczanie szybkości logowania         | PASS                      |
| #05   | Walidacja danych wejściowych API         | PASS                      |
| #06   | Unieważnianie sesji                      | PASS                      |
| #07   | Rotacja tokenów klientów                 | PASS                      |
| #08   | Obsługa adresów IP / sieci offline       | PASS                      |
| #09   | Odzyskiwanie zadań / punkty kontrolne    | PASS                      |
| #10   | Odporność APT                            | PASS                      |
| #11   | Wykrywanie ponownego uruchomienia Arch   | PASS                      |
| #12   | Testy jednostkowe / walidacja wyników API | PASS                     |
| #13   | Testy symulacyjne                        | PASS                      |
| #14   | Ciągła integracja                        | PASS                      |
| #15   | Logowanie aplikacji / audytu             | PASS                      |
| #16   | Wersjonowanie / wydania                  | Sprawdź bieżące wydania i tagi |
| #17   | Kontrola dostępu oparta na rolach        | PASS                      |

Mechanizmy bezpieczeństwa technicznego przejrzane w audytach #01–#15 i #17 zostały zaliczone.

Dostępność wydań i tagów może się zmieniać niezależnie od tego przewodnika. Aktualny stan sprawdź w [Releases](https://github.com/NovaForgeCtrl/LUMS/releases) i na liście [tagów](https://github.com/NovaForgeCtrl/LUMS/tags) repozytorium.

Żadnego wyniku audytu bezpieczeństwa nie należy interpretować jako gwarancji, że LUMS jest wolny od podatności.

Bezpieczeństwo jest procesem ciągłym.

Zmiany w aplikacji, Agencie, zależnościach, konfiguracji kontenera, ekspozycji sieciowej, modelu uwierzytelniania lub architekturze wdrożenia powinny wywołać kolejny przegląd bezpieczeństwa dotkniętych mechanizmów.

---

# Podstawa bezpieczeństwa

Ta podstawa opisuje mechanizmy skonfigurowane w kodzie źródłowym i wytycznych wdrożeniowych. Nie dowodzi, że stosuje je konkretna instalacja; zweryfikuj efektywne ustawienia w środowisku docelowym.

Podstawa obejmuje:

* uwierzytelnianie po stronie serwera
* RBAC po stronie serwera
* hashowanie haseł Argon2
* skróty SHA-256 tokenów klientów
* ochronę CSRF
* ograniczanie szybkości logowania
* parametryzowany SQL
* walidowane dane wejściowe API
* kontrolowane wykonywanie menedżera pakietów
* odzyskiwanie zadań aktualizacji
* logowanie audytowe
* utwardzony runtime Docker
* HTTPS przez Nginx
* ekspozycję portu aplikacji tylko na loopback
* ograniczenia firewalla
* chronione sekrety produkcyjne
* przypięte zależności produkcyjne
* ograniczone uprawnienia systemu plików
* automatyczne testy bezpieczeństwa

Przyszłe zmiany powinny zachować te właściwości, chyba że celowa zmiana architektury zastąpi je równoważnym lub silniejszym mechanizmem.

---

# Konserwacja bezpieczeństwa

Mechanizmy bezpieczeństwa powinny być ponownie walidowane, gdy wprowadzane są istotne zmiany.

Przykłady obejmują:

* zmiany uwierzytelniania
* nowe role użytkowników
* nowe endpointy API
* zmiany zarządzania pakietami
* zmiany wykonywania Agenta
* migracje bazy danych
* aktualizacje zależności
* zmiany Dockerfile
* zmiany runtime kontenera
* zmiany reverse proxy
* zmiany firewalla
* zmiany zarządzania sekretami
* przygotowanie wydania

Testy bezpieczeństwa należy przeprowadzić przed opublikowaniem oficjalnego wydania.

Dokumentacja bezpieczeństwa powinna być aktualizowana za każdym razem, gdy zmienia się zweryfikowana podstawa bezpieczeństwa.

---

# Gotowość wydania

Pierwsze oficjalne wydanie LUMS zostanie utworzone dopiero po:

1. zakończeniu pracy implementacyjnej
2. zakończeniu przeglądu bezpieczeństwa
3. zakończeniu przeglądu dokumentacji
4. pomyślnym przejściu pełnego automatycznego zestawu testów
5. pomyślnym przejściu CI
6. zdefiniowaniu końcowej wersji
7. utworzeniu tagu Git
8. opublikowaniu GitHub Release

Do tego czasu LUMS pozostaje aktywnie rozwijanym projektem.

---

# Oświadczenie końcowe

LUMS jest zaprojektowany jako kontrolowana platforma zarządzania aktualizacjami Linuksa, z bezpieczeństwem jako kluczowym zagadnieniem architektonicznym.

Model bezpieczeństwa nie opiera się na jednym mechanizmie ochronnym.

Zamiast tego uwierzytelnianie, autoryzacja, walidacja, kontrolowane wykonywanie, trwałość, odzyskiwanie, logowanie, izolacja kontenera, ograniczenia sieciowe i testy automatyczne współpracują jako warstwowe mechanizmy kontroli.

Projekt celowo przedkłada jawne egzekwowanie po stronie serwera nad bezpieczeństwem przez interfejs.

Podstawa bezpieczeństwa dokumentuje zweryfikowany stan implementacji, a nie historyczne zachowanie w trakcie rozwoju. Sama w sobie nie dowodzi, że konkretna instalacja stosuje opisane mechanizmy; zweryfikuj efektywne ustawienia w środowisku docelowym.

---

**LUMS — Linux Update Management without the noise.**

`segfault // override`
