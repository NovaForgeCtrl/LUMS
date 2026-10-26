# LUMS

**Zarządzanie aktualizacjami Linuksa bez zbędnego szumu.**

## Pierwsze kroki

LUMS centralnie zarządza aktualizacjami Linuksa. Serwer wyświetla klientów, zainstalowane oprogramowanie i dostępne aktualizacje. Agent na każdym zarządzanym systemie Linux wykonuje zatwierdzone operacje na pakietach, używając menedżera pakietów tego systemu. LUMS nie zastępuje APT w Debianie/Ubuntu ani pacmana w Arch Linux.

**Korzystasz tylko z istniejącej instalacji LUMS?** Otwórz adres podany przez administratora i zaloguj się na własne konto. Jeśli brakuje jakiejś funkcji, Twoje konto może nie mieć uprawnień do jej używania. Poproś administratora o pomoc; nie udostępniaj kont i nie używaj tokena klienta jako hasła do witryny.

**Instalujesz LUMS lub nim zarządzasz?** Zacznij od [przewodnika instalacji](<Instalacja i aktualizacje.md>), następnie przeczytaj [przewodnik administracji](<Administracja i kopie zapasowe.md>). Jeśli coś pójdzie nie tak, skorzystaj z [przewodnika rozwiązywania problemów](<Rozwiązywanie problemów.md>). Dostępne są również tłumaczenia, ale ich zakres może różnić się od angielskich oryginałów technicznych. [Indeks dokumentacji](../../README.md) wymienia dostępne wersje językowe.

Przebieg testów lub pomyślnie zbudowany obraz Docker **nie** jest instalacją produkcyjną. Wdrożenie produkcyjne wymaga również HTTPS, chronionego sekretu aplikacji, trwałych danych, zweryfikowanych kopii zapasowych i utwardzonego kontenera. Nie kopiuj poleceń produkcyjnych, dopóki nie sprawdzisz ich symboli zastępczych i ścieżek przechowywania względem własnej instalacji.

### Języki interfejsu webowego

Interfejs webowy oferuje język niemiecki, angielski (USA i Wielka Brytania), francuski, hiszpański, chiński uproszczony, japoński, polski, szwedzki, norweski bokmål i fiński. Wybierz język w prawym górnym rogu strony logowania. Jeśli nie wybierzesz żadnego, LUMS spróbuje użyć języka przeglądarki; po zalogowaniu pierwszeństwo ma język zapisany na Twoim koncie. Niektóre teksty techniczne lub dynamiczne mogą pozostać w swoim oryginalnym języku, gdy tłumaczenie nie jest dostępne. Przewodniki w formacie Markdown są oddzielone od interfejsu webowego i nie są tłumaczone automatycznie.

---

LUMS to serwer zarządzania aktualizacjami Linuksa zaprojektowany, aby zapewnić kontrolowane, audytowalne i bezpieczne zarządzanie oprogramowaniem i aktualizacjami dla klientów Linuksa.

Zamiast polegać na niekontrolowanej aktywności aktualizacyjnej po stronie klienta, LUMS zapewnia centralną warstwę zarządzania inwentarzem oprogramowania, wykrywaniem aktualizacji, operacjami na pakietach, zadaniami aktualizacji, monitorowaniem wykonania i raportowaniem wyników.

LUMS jest przeznaczony dla środowisk, w których aktualizacje powinny być **widoczne, kontrolowane, identyfikowalne i odtwarzalne**.

---

## Czym jest LUMS?

LUMS (**Linux Update Management Server**) składa się z serwera centralnego i lekkich klientów Linuksa.

Serwer zapewnia interfejs zarządzania, API, uwierzytelnianie, autoryzację, zarządzanie zadaniami, rejestrowanie audytu i trwały stan.

Agent po stronie klienta wykonuje lokalne operacje menedżera pakietów i raportuje wyniki z powrotem do serwera.

Podstawowa architektura to:

```text
                    ┌──────────────────────┐
                    │      Web Browser      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │     LUMS Server      │
                    │                      │
                    │ Web UI / API         │
                    │ Authentication       │
                    │ RBAC                 │
                    │ Job Management       │
                    │ Audit Logging        │
                    │ SQLite               │
                    └──────────┬───────────┘
                               │
                         HTTPS / API
                               │
              ┌────────────────┴────────────────┐
              │                                 │
              ▼                                 ▼
      ┌─────────────────┐             ┌─────────────────┐
      │   Linux Client  │             │   Linux Client  │
      │                 │             │                 │
      │ LUMS Agent      │             │ LUMS Agent      │
      │ Package Manager │             │ Package Manager │
      │ Watcher         │             │ Watcher         │
      └─────────────────┘             └─────────────────┘
```

---

## Dlaczego LUMS?

Systemy Linux już zapewniają doskonałe narzędzia do zarządzania pakietami.

LUMS nie próbuje ich zastąpić.

Zamiast tego LUMS zapewnia warstwę zarządzania wokół tych narzędzi, aby administratorzy mogli centralnie odpowiadać na pytania takie jak:

* Którzy klienci istnieją?
* Jakie oprogramowanie jest zainstalowane?
* Jakie aktualizacje są dostępne?
* Które pakiety należy zainstalować lub usunąć?
* Które zadania aktualizacji są uruchomione?
* Co się stało podczas aktualizacji?
* Czy klient pomyślnie zaraportował wynik?
* Czy wymagany był restart?
* Czy przerwane zadanie może bezpiecznie zostać wznowione?
* Kto zainicjował działanie administracyjne?

Celem nie jest ukrycie bazowego menedżera pakietów Linuksa.

Celem jest uczynienie jego działania **zarządzalnym i audytowalnym**.

---

## Główne funkcje

### Zarządzanie klientami

LUMS utrzymuje zarejestrowanych klientów Linuksa i ich stan uwierzytelniania.

Każdy klient otrzymuje indywidualny token uwierzytelniania.

Tokeny klientów nie są przechowywane jako poświadczenia w postaci zwykłego tekstu. Serwer przechowuje skrót SHA-256 i weryfikuje przychodzące uwierzytelnianie klienta względem tego skrótu.

Administratorzy mogą:

* rejestrować klientów
* wyłączać klientów
* rotować tokeny klientów
* sprawdzać stan klientów
* monitorować raportowanie klientów

---

### Inwentarz oprogramowania

Klienci raportują swoje zainstalowane oprogramowanie do serwera LUMS.

Serwer przechowuje inwentarz i udostępnia go poprzez interfejs zarządzania.

Widok zainstalowanego oprogramowania jest celowo oddzielony od wyszukiwania w zarządzaniu pakietami.

Pozwala to administratorom i użytkownikom w trybie tylko do odczytu przeglądać zainstalowane oprogramowanie bez automatycznego ujawniania operacji zarządzania pakietami.

---

### Inwentarz aktualizacji

Klienci okresowo sprawdzają, czy dostępne są aktualizacje pakietów.

Serwer przechowuje zaraportowane informacje o aktualizacjach i udostępnia je autoryzowanym użytkownikom.

Informacje o aktualizacjach mogą być podstawą kontrolowanych zadań aktualizacji.

---

### Zarządzanie pakietami

LUMS zapewnia operacje zarządzania pakietami poprzez agenta klienta.

Obsługiwane operacje na pakietach obejmują:

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

Warstwa zarządzania pakietami abstrahuje bazowy menedżer pakietów.

Obecnie obsługiwane rodziny menedżerów pakietów to:

* **Debian / Ubuntu:** APT / dpkg
* **Arch Linux:** pacman

Wyszukiwanie pakietów jest również dostępne poprzez LUMS.

Żądania wyszukiwania są wysyłane do docelowego klienta, wykonywane przy użyciu lokalnego menedżera pakietów i zwracane do serwera w celu wyświetlenia.

---

### Zadania aktualizacji

Operacje aktualizacji są reprezentowane jako trwałe zadania.

Zadanie może zawierać jedną lub więcej operacji na pakietach i utrzymuje stan wykonania po stronie serwera.

Ogólny cykl życia to:

```text
PENDING
   │
   ▼
RUNNING
   │
   ├──────────────► SUCCESS
   │
   └──────────────► FAILED
```

Wyniki na poziomie pakietów są śledzone niezależnie, dzięki czemu przerwane zadania mogą zostać wznowione bez niepotrzebnego powtarzania operacji, które już zakończyły się pomyślnie.

---

### Kontrolowane wykonanie

LUMS nie wykonuje dowolnych poleceń powłoki dostarczonych przez interfejs webowy.

Serwer tworzy strukturalne zadania przy użyciu zwalidowanych akcji i nazw pakietów.

Agent klienta mapuje te akcje na odpowiednią lokalną operację menedżera pakietów.

Tworzy to celową granicę pomiędzy:

```text
Web UI
   ↓
API
   ↓
Validated Job
   ↓
Agent
   ↓
Package Manager
```

---

### Wykonanie uwzględniające bezczynność

LUMS może odroczyć wykonanie aktualizacji, gdy klient jest uważany za aktywny.

Obecny próg bezczynności wynosi **300 sekund**.

Tam, gdzie jest to obsługiwane, agent korzysta z informacji o sesji/bezczynności lokalnego systemu poprzez `loginctl`.

Jeśli wykrywanie bezczynności jest niedostępne, LUMS nie udaje, że klient jest bezczynny.

To rozróżnienie jest ważne, ponieważ **nieznany stan bezczynności nie jest tym samym co potwierdzony stan bezczynności**.

---

### Wznawianie zadań

Zadania aktualizacji są zaprojektowane tak, aby przetrwać przerwy.

Serwer utrzymuje trwały stan zadań i elementów pakietów.

Podczas wznawiania pomyślnie zakończone elementy pakietów nie są niepotrzebnie wykonywane ponownie.

Zapewnia to model wykonania podobny do punktów kontrolnych dla operacji wielopakietowych.

Celem jest:

> **Wznowić zadanie, a nie bezmyślnie uruchomić całe zadanie od nowa.**

---

### Wykrywanie restartu

Niektóre operacje na pakietach mogą wymagać restartu systemu.

Dlatego LUMS traktuje wykrywanie restartu jako część obsługi wyniku aktualizacji, zamiast zakładać, że pomyślne zakończenie menedżera pakietów zawsze oznacza, że system jest w pełni operacyjny.

Klient raportuje wykryte wymaganie restartu z powrotem do serwera.

---

### Uwierzytelnianie klienta

Komunikacja klienta jest uwierzytelniana przy użyciu tokenów dla poszczególnych klientów.

Tokeny są:

* indywidualnie przypisywane
* rotowalne
* przechowywane po stronie serwera wyłącznie jako skróty SHA-256
* walidowane przed akceptacją raportów klientów

Rotacja tokenów pozwala administratorowi unieważnić wcześniej wydane poświadczenie klienta bez ponownego tworzenia klienta.

---

### Audytowalność

Działania administracyjne i istotne dla bezpieczeństwa są rejestrowane poprzez system dziennika audytu LUMS.

Ścieżka audytu ma odpowiadać na pytania:

```text
Kto?
Co?
Kiedy?
Wobec jakiego obiektu?
Z jakim wynikiem?
```

Obejmuje to operacje wrażliwe na bezpieczeństwo, takie jak działania związane z uwierzytelnianiem, zarządzanie klientami, zarządzanie użytkownikami i tworzenie zadań aktualizacji.

---

## Zasada projektowa

LUMS kieruje się prostą zasadą:

> **Uczyń zarządzanie aktualizacjami Linuksa widocznym, kontrolowanym, odtwarzalnym i audytowalnym — bez ukrywania narzędzi Linuksa znajdujących się pod spodem.**

## Architektura

LUMS rozdziela zarządzanie, wykonanie i trwałość na jasno zdefiniowane komponenty.

Serwer odpowiada za orkiestrację i politykę.

Klient odpowiada za interakcję z lokalnym systemem.

Menedżer pakietów pozostaje odpowiedzialny za faktyczne instalowanie, usuwanie lub aktualizowanie oprogramowania.

To rozdzielenie jest celowe.

```text
Browser
   │
   │ HTTPS
   ▼
┌──────────────────────────────────────────┐
│                LUMS Server                │
│                                          │
│  Web UI                                  │
│  Authentication / Sessions               │
│  RBAC                                    │
│  API                                     │
│  Client Management                       │
│  Package Search                          │
│  Update Job Management                   │
│  Audit Logging                            │
│  SQLite Persistence                       │
└───────────────────┬──────────────────────┘
                    │
                    │ HTTPS / Client API
                    ▼
┌──────────────────────────────────────────┐
│               LUMS Agent                  │
│                                          │
│  Authentication                          │
│  Inventory Reporting                     │
│  Update Detection                        │
│  Package Search                          │
│  Job Execution                           │
│  Result Reporting                        │
│  Reboot Detection                        │
│  Idle Detection                          │
└───────────────────┬──────────────────────┘
                    │
                    ▼
          ┌────────────────────┐
          │ Package Manager    │
          │                    │
          │ APT / dpkg         │
          │ pacman             │
          └────────────────────┘
```

---

## Komponenty serwera

Serwer LUMS zapewnia centralną warstwę zarządzania.

### Aplikacja webowa

Aplikacja webowa zapewnia interfejs administracyjny do:

* zarządzania klientami
* inwentarza oprogramowania
* informacji o aktualizacjach
* zadań aktualizacji
* zarządzania pakietami
* historii aktualizacji
* zarządzania użytkownikami
* konserwacji systemu

Interfejs respektuje rolę RBAC bieżącego użytkownika.

Dlatego widoczność we frontendzie jest dostosowana do uprawnień użytkownika, ale autoryzacja jest zawsze egzekwowana także po stronie serwera.

---

### API

API łączy interfejs webowy i klientów Linuksa z logiką aplikacji po stronie serwera.

Obsługuje operacje takie jak:

* rejestracja i zarządzanie klientami
* raporty klientów
* wyszukiwanie pakietów
* wyniki wyszukiwania pakietów
* zadania aktualizacji
* wyniki zadań
* zarządzanie użytkownikami
* zdarzenia audytu

Punkty końcowe API walidują swoje dane wejściowe przed wykonaniem operacji zmieniających stan.

---

### Uwierzytelnianie i sesje

Użytkownicy administracyjni uwierzytelniają się poprzez aplikację webową LUMS.

Sesje są kontrolowane przez serwer i obsługują jawne unieważnianie sesji.

Bezpieczeństwo uwierzytelniania obejmuje:

* hashowanie haseł z użyciem Argon2
* zarządzanie sesjami
* unieważnianie sesji
* ograniczanie szybkości logowania
* ochronę CSRF
* autoryzację opartą na rolach

Uwierzytelnianie klientów jest oddzielone od uwierzytelniania administracyjnego.

---

### RBAC

LUMS łączy szablony ról z uprawnieniami dla poszczególnych użytkowników. Szablony Administrator, Operator i Viewer zapewniają początkowe zestawy uprawnień, które można dostosować dla każdego konta.

Autoryzacja jest egzekwowana na serwerze przy użyciu uprawnień zapisanych na koncie.

Frontend dodatkowo ukrywa funkcje, na które uprawnienia użytkownika nie pozwalają.

Oznacza to, że ukrycie przycisku nigdy nie jest traktowane jako granica bezpieczeństwa.

---

### Trwałość SQLite

LUMS używa SQLite do trwałego stanu aplikacji.

Baza danych przechowuje informacje takie jak:

* użytkownicy
* sesje
* klienci
* stan uwierzytelniania klientów
* inwentarz oprogramowania
* dostępne aktualizacje
* zadania aktualizacji
* wyniki zadań na poziomie pakietów
* żądania i wyniki wyszukiwania pakietów
* informacje audytu

Aplikacja jawnie włącza wymuszanie kluczy obcych SQLite dla połączeń z bazą danych.

Obecna produkcyjna baza SQLite to:

```text
journal_mode = wal
busy_timeout = 5000
synchronous = 2
foreign_keys = ON
```

LUMS używa trybu WAL SQLite w obecnej konfiguracji produkcyjnej.

---

## Architektura kontenera

Serwer LUMS jest wdrażany jako utwardzony kontener Docker.

Kontener aplikacji jest celowo traktowany jako jednorazowy.

Trwały stan aplikacji jest przechowywany w dedykowanym wolumenie Docker:

```text
lums-data
```

Kontener produkcyjny używa systemu plików głównego tylko do odczytu.

Zapisywalne lokalizacje są celowo ograniczone do wymaganych ścieżek wykonania i trwałego przechowywania.

Produkcyjna podstawa bezpieczeństwa obejmuje:

```text
system plików główny tylko do odczytu
wszystkie uprawnienia Linux usunięte
no-new-privileges
ograniczony /tmp
ograniczony /run
montaż sekretu tylko do odczytu
dedykowany trwały wolumen danych
użytkownik aplikacji inny niż root
```

Aplikacja jest wewnętrznie dostępna poprzez:

```text
127.0.0.1:5050
```

Zewnętrzny dostęp HTTPS jest zapewniony przez reverse proxy.

---

## Komponenty trwałe i jednorazowe

LUMS rozdziela stan trwały od wymiennych komponentów wykonawczych.

```text
Persistent
├── SQLite database
├── client state
├── user state
├── job state
└── audit state

Disposable
├── Docker container
├── application process
└── generated runtime state
```

Zastąpienie kontenera aplikacji nie usuwa zatem w sposób nieodłączny bazy danych LUMS.

To rozdzielenie jest ważne dla aktualizacji i wznawiania.

---

## Architektura klienta

Klient Linuksa składa się z kilku współpracujących komponentów.

### LUMS Agent

Agent odpowiada za interakcję z serwerem LUMS i lokalnym systemem Linux.

Obecna wersja agenta:

```text
1.7.0
```

Agent obsługuje:

* uwierzytelnianie
* zbieranie inwentarza
* wykrywanie aktualizacji
* wyszukiwanie pakietów
* operacje na pakietach
* wykonanie zadań aktualizacji
* raportowanie wyników
* wykrywanie restartu
* obsługę stanu bezczynności

---

### Warstwa menedżera pakietów

Warstwa menedżera pakietów zapewnia kontrolowaną abstrakcję wokół natywnego menedżera pakietów Linuksa.

Agent nie wymaga, aby LUMS zastąpił menedżera pakietów.

Zamiast tego:

```text
LUMS Action
     │
     ▼
Package Manager Abstraction
     │
     ├── Debian / Ubuntu → APT / dpkg
     │
     └── Arch Linux      → pacman
```

Pozwala to utrzymać obsługę pakietów specyficzną dla dystrybucji wewnątrz klienta.

---

### Watcher wykonania

Watcher monitoruje wykonanie zadań aktualizacji na kliencie.

Obecna wersja watchera:

```text
1.2.1
```

Watcher współpracuje z agentem i stanem zadań po stronie serwera.

Jego celem jest zapewnienie, że zadania, które powinny zostać wykonane, nie pozostają w nieskończoność nieprzetworzone.

---

## Ścieżka raportowania

Normalne raportowanie klienta podąża w tym kierunku:

```text
Linux Client
    │
    │ inventory / update information
    ▼
LUMS API
    │
    ▼
SQLite
    │
    ▼
Web UI
```

Na przykład sprawdzenie aktualizacji wykonane przez klienta generuje informacje, które są raportowane do serwera i przechowywane jako bieżący stan aktualizacji klienta.

Przeglądarka nie odpytuje bezpośrednio menedżera pakietów klienta.

---

## Ścieżka wyszukiwania pakietów

Wyszukiwanie pakietów podlega innemu przepływowi żądanie/odpowiedź:

```text
Browser
   │
   │ search request
   ▼
LUMS Server
   │
   │ package-search request
   ▼
Linux Client
   │
   │ APT / pacman search
   ▼
Linux Client
   │
   │ search result
   ▼
LUMS Server
   │
   ▼
Browser
```

Serwer nie musi zatem utrzymywać pełnego zdalnego indeksu repozytorium pakietów dla każdego klienta.

Wyszukiwanie jest wykonywane przy użyciu własnego środowiska zarządzania pakietami klienta.

---

## Ścieżka wykonania aktualizacji

Zadanie aktualizacji podlega ogólnej architekturze:

```text
Browser
   │
   │ create job
   ▼
LUMS API
   │
   │ validate request
   ▼
SQLite
   │
   │ persistent job
   ▼
Linux Client
   │
   │ execute action
   ▼
APT / dpkg / pacman
   │
   │ result
   ▼
Linux Client
   │
   │ validated result
   ▼
LUMS API
   │
   ▼
SQLite
   │
   ▼
Browser
```

Tworzy to centralny łańcuch wykonania LUMS:

> **Browser → API → SQLite → Agent → Package Manager → Result → SQLite → UI**

---

## Atomowe przejmowanie zadań

Zadania aktualizacji są trwałymi obiektami po stronie serwera.

Przed wykonaniem agent musi uzyskać zadanie kwalifikujące się do wykonania.

Przejmowanie zadań jest wykonywane atomowo, aby to samo oczekujące zadanie nie zostało niechcący przejęte przez wiele ścieżek wykonania.

Jest to szczególnie ważne, gdy zaangażowane są timery, ponowienia, wznawianie lub wiele procesów po stronie klienta.

---

## Wykonanie zadania

Serwer tworzy strukturalne zadania.

Agent klienta interpretuje obsługiwane akcje zadania i wykonuje odpowiednią operację lokalną.

Obsługiwane akcje na pakietach to:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Nazwy pakietów są walidowane przed utworzeniem zadania pakietowego.

Agent nie traktuje nazw pakietów jako dowolnych fragmentów powłoki.

---

## Abstrakcja menedżera pakietów

Operacje na pakietach są celowo zaimplementowane za abstrakcją menedżera pakietów.

Utrzymuje to model zadań LUMS wyższego poziomu niezależny od poleceń specyficznych dla dystrybucji.

Na przykład:

```text
INSTALL_PACKAGE
       │
       ├── Debian / Ubuntu → APT
       │
       └── Arch Linux      → pacman
```

Ta sama zasada dotyczy usuwania i aktualizacji pakietów.

---

## Debian / Ubuntu

W systemach z rodziny Debian LUMS używa natywnych narzędzi APT/dpkg.

Typowe obowiązki obejmują:

* wyszukiwanie pakietów
* wyszukiwanie metadanych pakietów
* instalację pakietów
* usuwanie pakietów
* aktualizacje pakietów
* aktualizacje systemu
* wykrywanie aktualizacji

Agent LUMS nie zastępuje APT.

Zapewnia kontrolowaną orkiestrację wokół niego.

---

## Arch Linux

W systemach Arch Linux LUMS używa natywnego menedżera pakietów pacman.

Typowe obowiązki obejmują:

* wyszukiwanie pakietów
* wyszukiwanie metadanych pakietów
* instalację pakietów
* usuwanie pakietów
* aktualizacje pakietów
* aktualizacje systemu
* wykrywanie aktualizacji

Zachowanie specyficzne dla dystrybucji pozostaje wewnątrz warstwy menedżera pakietów.

---

## Wyszukiwanie pakietów

Wyszukiwanie pakietów jest oddzielone od inwentarza zainstalowanego oprogramowania.

To rozróżnienie jest ważne:

```text
Installed Software
        │
        └── What is already installed?

Package Management Search
        │
        └── What package can the client currently find?
```

Wyniki wyszukiwania mogą zawierać informacje o pakietach takie jak:

* nazwa pakietu
* wersja
* opis
* informacje o repozytorium, gdy są dostępne

Wyniki wyszukiwania są zwracane do serwera LUMS i wyświetlane w interfejsie zarządzania pakietami.

---

## Uprawnienia do zarządzania pakietami

Zarządzanie pakietami jest operacją uprzywilejowaną.

Obecny model uprawnień to:

```text
Administrator → allowed
Operator      → allowed
Viewer        → not allowed
```

Viewer nadal może przeglądać zainstalowane oprogramowanie.

Sam interfejs zarządzania pakietami jest ukryty dla Viewerów, a odpowiednie punkty końcowe mutacji po stronie serwera egzekwują autoryzację niezależnie.

---

## Obsługa wyników aktualizacji

LUMS traktuje wynik operacji aktualizacji jako stan strukturalny, a nie tylko wyświetlanie surowego wyjścia polecenia.

Istotne informacje mogą obejmować:

* sukces lub porażkę
* wynik na poziomie pakietu
* stan wykonania
* informacje o błędach
* wymaganie restartu
* znaczniki czasu zakończenia

Pozwala to serwerowi utrzymywać sensowną historię aktualizacji.

---

## Wykrywanie restartu

Po operacjach na pakietach klient sprawdza, czy operacja wskazuje, że wymagany jest restart.

Wynik jest raportowany do serwera jako część wyniku zadania.

Dlatego wymaganie restartu pozostaje powiązane z operacją aktualizacji, zamiast ginąć w sesji terminala po stronie klienta.

---

## Granica uwierzytelniania klienta

API klienta używa innego mechanizmu uwierzytelniania niż administracyjne sesje webowe.

```text
Administrative User
        │
        ▼
 Web Authentication
        │
        ▼
    LUMS Server

Linux Client
        │
        ▼
 Client Token
        │
        ▼
    LUMS Server
```

To rozdzielenie zapobiega temu, aby administracyjne sesje przeglądarki i poświadczenia klientów stały się wymiennymi mechanizmami uwierzytelniania.

---

## Ścieżka audytu

Działania istotne dla bezpieczeństwa i administracyjne są rejestrowane przez system audytu po stronie serwera.

Ścieżka audytu uzupełnia normalne rejestrowanie aplikacji.

Rejestrowanie odpowiada na pytania dotyczące zachowania aplikacji.

Rejestrowanie audytu dodatkowo rejestruje ważne działania administracyjne i ich kontekst.

To rozróżnienie jest przydatne przy badaniu zmian w klientach, użytkownikach, stanie uwierzytelniania lub zadaniach aktualizacji.

---

## Zasada operacyjna

LUMS celowo rozdziela:

```text
Management
     │
     ▼
Policy / Authorization
     │
     ▼
Job
     │
     ▼
Client Execution
     │
     ▼
Native Package Manager
```

Każda warstwa ma zdefiniowaną odpowiedzialność.

Serwer zarządza.

Agent wykonuje.

Menedżer pakietów dokonuje rzeczywistej zmiany systemu.

Wynik podróżuje z powrotem przez ten sam kontrolowany łańcuch.

## Kontrola dostępu oparta na rolach

LUMS używa trzech ról administracyjnych:

```text
Administrator
Operator
Viewer
```

Autoryzacja jest egzekwowana po stronie serwera.

Frontend dodatkowo dostosowuje widoczny interfejs do uprawnień użytkownika, ale widoczność we frontendzie nigdy nie jest traktowana jako granica bezpieczeństwa.

### Administrator

Administratorzy mają dostęp do:

* przeglądania klientów
* przeglądania zainstalowanego oprogramowania
* przeglądania dostępnych aktualizacji
* tworzenia i wykonywania zadań aktualizacji
* przeglądania historii aktualizacji
* korzystania z zarządzania pakietami
* wykonywania konserwacji systemu
* tworzenia i wyłączania klientów
* rotacji tokenów klientów
* tworzenia i zarządzania użytkownikami
* zarządzania rolami i dostępem użytkowników

### Operator

Operatorzy mają dostęp do:

* przeglądania klientów
* przeglądania zainstalowanego oprogramowania
* przeglądania dostępnych aktualizacji
* tworzenia i wykonywania zadań aktualizacji
* przeglądania historii aktualizacji
* korzystania z zarządzania pakietami
* wykonywania konserwacji systemu

Operatorzy nie mają dostępu do:

* zarządzania użytkownikami
* administracji rolami
* tworzenia lub wyłączania klientów
* rotacji tokenów klientów

### Viewer

Viewerzy mają dostęp tylko do odczytu do:

* klientów
* zainstalowanego oprogramowania

Następujące funkcje są niedostępne dla Viewerów:

* zarządzanie dostępnymi aktualizacjami
* zadania aktualizacji
* historia aktualizacji
* zarządzanie pakietami
* konserwacja systemu
* inne operacje administracyjne zmieniające stan

Serwer niezależnie egzekwuje te ograniczenia.

---

## Zarządzanie użytkownikami

LUMS zapewnia zarządzanie użytkownikami kontom z uprawnieniem `users.manage`.

Użytkownicy z tym uprawnieniem mogą tworzyć konta przy użyciu szablonu roli, a następnie przypisywać uprawnienia indywidualnie lub jawnie zastosować ten szablon. Nowe konta zaczynają bez uprawnień; edytor uprawnień otwiera się po utworzeniu. Menedżerowie użytkowników mogą również zapisywać prywatne notatki administracyjne, które nie są widoczne dla właściciela konta.

Administratorzy z `backups.manage` mogą tworzyć zwalidowane kopie zapasowe bazy danych `.db` lub `.db.gz` w katalogu skonfigurowanym na serwerze i wybierać bezpieczny podfolder w tej zamontowanej lokalizacji. Zobacz [`administration.md`](<Administracja i kopie zapasowe.md>) oraz wbudowany w aplikację przewodnik przywracania w formacie Markdown dla konfiguracji przechowywania w Dockerze i odzyskiwania.

Hasła użytkowników są przechowywane przy użyciu hashowania haseł Argon2, a nie w postaci zwykłego tekstu lub odwracalnego szyfrowania.

Operacje zarządzania użytkownikami są chronione przez:

* uwierzytelnianie
* autoryzację opartą na uprawnieniach
* ochronę CSRF
* walidację danych wejściowych
* sprawdzanie duplikatów użytkowników
* rejestrowanie audytu

Interfejs zarządzania użytkownikami nie jest udostępniany bez `users.manage`.

---

## Bezpieczeństwo sesji

Uwierzytelnianie administracyjne używa obsługi sesji po stronie serwera.

Bezpieczeństwo sesji obejmuje:

* uwierzytelniony stan sesji
* unieważnianie sesji
* ochronę CSRF dla żądań zmieniających stan
* ograniczanie szybkości logowania
* egzekwowanie wyłączonych kont
* sprawdzanie ról

Unieważnienie sesji unieważnia odpowiedni uwierzytelniony stan, a nie tylko ukrywa interfejs użytkownika.

---

## Ograniczanie szybkości logowania

Powtarzające się nieudane próby logowania podlegają progresywnemu ograniczaniu szybkości.

Obecne progi to:

```text
5 attempts  → 30 seconds
6 attempts  → 60 seconds
7 attempts  → 120 seconds
8+ attempts → 300 seconds
```

Odpowiedni stan jest trwale zapisywany w SQLite.

Pomyślne uwierzytelnienie czyści odpowiedni stan niepowodzenia.

Zapobiega to wykorzystaniu prostego restartu aplikacji do obejścia ochrony logowania.

---

## Bezpieczeństwo tokenów klientów

Każdy zarejestrowany klient ma własny token uwierzytelniania.

Serwer przechowuje token jako skrót SHA-256.

Oryginalny token nie jest wymagany do normalnej walidacji po stronie serwera.

Rotacja tokenów pozwala administratorom unieważnić istniejące poświadczenie i wydać zamiennik.

Tworzy to jasny cykl życia:

```text
Create
  │
  ▼
Use
  │
  ▼
Rotate
  │
  ▼
Old token invalid
```

---

## Bezpieczeństwo API

LUMS waliduje dane wejściowe API przed wykonaniem operacji zmieniających stan.

Kontrole bezpieczeństwa obejmują:

* uwierzytelnianie
* autoryzację uprawnień dla poszczególnych użytkowników
* ochronę CSRF, gdy ma to zastosowanie
* walidację danych wejściowych
* walidację nazw pakietów
* strukturalne akcje zadań
* parametryzowane zapytania do bazy danych
* kontrolowaną obsługę błędów

Aplikacja nie używa nazw pakietów dostarczonych przez użytkownika jako nieograniczonych poleceń powłoki.

---

## Ochrona przed wstrzykiwaniem SQL

Operacje na bazie danych używają parametryzowanych instrukcji SQL.

Wartości kontrolowane przez użytkownika nie są bezpośrednio łączone z zapytaniami SQL.

Dotyczy to obszarów takich jak:

* uwierzytelnianie
* zarządzanie klientami
* zarządzanie użytkownikami
* wyszukiwanie pakietów
* zadania aktualizacji
* dane audytu
* raportowanie wyników

Celem jest utrzymanie wartości danych oddzielnie od instrukcji SQL.

---

## Podstawa bezpieczeństwa SQLite

Obecna konfiguracja produkcyjna SQLite to:

```text
journal_mode = wal
busy_timeout = 5000
synchronous = 2
foreign_keys = ON
```

Wymuszanie kluczy obcych jest jawnie włączane przez aplikację dla połączeń z bazą danych.

Obecna konfiguracja używa trybu WAL.

Baza danych jest przechowywana w trwałym wolumenie Docker, a nie wewnątrz jednorazowego systemu plików kontenera aplikacji.

---

## Wznawianie zadań i punkty kontrolne

LUMS traktuje zadania aktualizacji jako trwałe maszyny stanów.

Zadanie wielopakietowe może zawierać kilka indywidualnych operacji na pakietach.

Każdy element pakietu może osiągnąć własny stan wyniku.

Jeśli wykonanie zostanie przerwane, wznawianie może rozróżnić pomiędzy:

```text
already successful
        │
        └── do not unnecessarily repeat

not completed
        │
        └── eligible for recovery
```

Zmniejsza to ryzyko bezmyślnego powtarzania zakończonych operacji na pakietach po przerwie.

---

## Kontrolowane wykonanie aktualizacji

LUMS celowo ogranicza akcje, które można zlecić poprzez API zadań aktualizacji.

Obsługiwane akcje to:

```text
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Serwer waliduje akcję i odpowiednie informacje o pakiecie przed utworzeniem zadania.

Agent następnie mapuje strukturalną akcję na odpowiednią operację menedżera pakietów.

Pozwala to uniknąć przekształcenia systemu aktualizacji w ogólny mechanizm zdalnego wykonywania poleceń.

---

## Operacje na pakietach

Operacje na pakietach są wykonywane poprzez natywny menedżer pakietów klienta.

### Instalacja

Zwalidowana nazwa pakietu jest przekazywana do abstrakcji menedżera pakietów w celu instalacji.

### Usuwanie

Zwalidowana nazwa pakietu jest przekazywana do abstrakcji menedżera pakietów w celu usunięcia.

### Aktualizacja pakietu

Konkretny pakiet może zostać zaktualizowany, gdy klient zgłosi go jako dostępną aktualizację.

### Aktualizacja systemu

Operacja aktualizacji systemu deleguje proces aktualizacji do natywnego menedżera pakietów.

Wszystkie operacje zwracają strukturalne wyniki do serwera LUMS.

---

## Bezpieczeństwo menedżera pakietów

LUMS traktuje menedżera pakietów jako uprzywilejowany komponent lokalny.

Dlatego agent nie próbuje samodzielnie emulować zachowania menedżera pakietów.

Zamiast tego:

1. waliduje żądaną operację
2. wybiera odpowiednią implementację menedżera pakietów
3. wykonuje kontrolowaną operację
4. przechwytuje wynik
5. raportuje wynik do serwera

Zachowanie specyficzne dla dystrybucji pozostaje odizolowane wewnątrz warstwy menedżera pakietów.

---

## Obsługa restartów

Niektóre operacje na pakietach mogą wymagać restartu.

LUMS rejestruje wymagania restartu jako część wyników zadań aktualizacji.

Pozwala to administratorom rozróżnić pomiędzy:

```text
Update completed
```

a:

```text
Update completed
Reboot required
```

Dlatego wymaganie restartu jest częścią stanu operacyjnego, a nie traktowane jako niepowiązane powiadomienie.

---

## Rejestrowanie audytu

LUMS utrzymuje ścieżkę audytu aplikacji dla ważnych działań administracyjnych i istotnych dla bezpieczeństwa.

Przykłady obejmują:

* zdarzenia związane z uwierzytelnianiem
* zarządzanie klientami
* operacje na tokenach
* zarządzanie użytkownikami
* tworzenie zadań aktualizacji
* zmiany stanu wrażliwe na bezpieczeństwo

Rejestrowanie audytu jest oddzielone od zwykłego rejestrowania diagnostycznego.

Dzienniki diagnostyczne pomagają rozwiązywać problemy z aplikacją.

Rekordy audytu zapewniają historię administracyjną istotnych działań.

---

## Utwardzanie bezpieczeństwa

Obecne wdrożenie obejmuje wiele warstw utwardzania.

### Utwardzanie kontenera

Kontener produkcyjny używa:

* wykonania aplikacji bez uprawnień roota
* systemu plików głównego tylko do odczytu
* usuniętych uprawnień Linuksa
* `no-new-privileges`
* ograniczonych systemów plików tymczasowych
* montażu sekretu tylko do odczytu
* dedykowanego trwałego wolumenu danych

### Utwardzanie sieci

Kontener aplikacji jest powiązany z loopbackiem na hoście:

```text
127.0.0.1:5050
```

Dlatego port aplikacji nie jest bezpośrednio udostępniany jako usługa LAN.

Dostęp zewnętrzny jest obsługiwany przez reverse proxy HTTPS.

Firewall nie udostępnia wewnętrznego portu aplikacji.

### Bezpieczeństwo transportu

Dostęp administracyjny jest zapewniony poprzez HTTPS.

Reverse proxy obsługuje zewnętrzną terminację TLS.

Żądania HTTP są przekierowywane do HTTPS.

### Sekrety i konfiguracja

Wrażliwe poświadczenia wykonawcze są przechowywane poza drzewem źródłowym aplikacji.

Sekret produkcyjny jest montowany w kontenerze jako plik sekretu tylko do odczytu.

Reguły repozytorium i kontekstu budowania Dockera zapobiegają niezamierzonemu włączeniu typowych artefaktów kopii zapasowych, sekretów, baz danych i certyfikatów do kontekstu budowania obrazu.

### Bezpieczeństwo zależności i budowania

Zależności Pythona produkcyjne są przypięte.

Obraz bazowy Pythona produkcyjny jest przypięty przez digest.

Kontekst budowania Dockera jest ograniczony poprzez `.dockerignore`.

Te kontrole poprawiają powtarzalność budowania i zmniejszają przypadkowe włączanie wrażliwych plików.

---

## Status audytu bezpieczeństwa

Przegląd bezpieczeństwa LUMS objął następujące obszary:

* wymuszanie kluczy obcych SQLite
* konfigurację środowiska wykonawczego SQLite
* limit czasu aktualizacji i obsługę procesów
* ograniczanie szybkości logowania
* walidację danych wejściowych API
* unieważnianie sesji
* rotację tokenów klientów
* obsługę offline/IP
* wznawianie zadań i punkty kontrolne
* solidność APT
* wykrywanie restartu Arch
* walidację testów jednostkowych i wyników API
* testy symulacyjne
* ciągłą integrację
* rejestrowanie aplikacji i audytu
* obsługę wersjonowania i wydań
* RBAC
* bezpieczeństwo sesji i CSRF
* bezpieczeństwo poświadczeń
* bezpieczeństwo zależności i budowania
* utwardzanie Dockera/kontenera
* ochronę sekretów i kontekstu budowania
* bezpieczeństwo HTTP/transportu
* uprawnienia systemu plików/środowiska wykonawczego
* ekspozycję sieci
* higienę artefaktów repozytorium

Pozostały przegląd dokumentacji jest obsługiwany oddzielnie jako część końcowego procesu gotowości wydania.

---

## Testowanie i CI

LUMS zawiera testy automatyczne obejmujące podstawowe zachowanie aplikacji i kontrole bezpieczeństwa.

Uruchom pełny zestaw testów z katalogu głównego repozytorium:

```bash
./.venv-test/bin/pytest -q
```

Liczba testów zmienia się w czasie. Wymaganym wynikiem jest pomyślne zakończenie całego zestawu bez błędów. Zestaw testów obejmuje pokrycie obszarów takich jak:

* uwierzytelnianie
* RBAC
* zarządzanie klientami
* zarządzanie użytkownikami
* wyszukiwanie pakietów
* zadania aktualizacji
* walidacja wyników zadań
* zachowanie bezpieczeństwa
* zachowanie API

Ciągła integracja uruchamia automatyczny zestaw testów, zanim zmiany zostaną uznane za gotowe.

Wymagane jest pomyślne uruchomienie testów, ale testy są tylko jedną częścią procesu wydania.

Proces wydania wymaga również:

```text
Implementation
    ↓
Security Review
    ↓
Documentation Review
    ↓
Full Test Suite
    ↓
CI
    ↓
Version
    ↓
Git Tag
    ↓
GitHub Release
```

---

## Status rozwoju

LUMS jest obecnie w aktywnym rozwoju.

Podstawowa architektura zarządzania, model wykonania po stronie klienta, zarządzanie pakietami, RBAC, utwardzanie bezpieczeństwa i mechanizmy wznawiania są zaimplementowane.

Projekt celowo nie jest uznawany za ukończone wydanie tylko dlatego, że aplikacja działa.

Gotowość wydania wymaga również, aby otaczająca dokumentacja i procedury operacyjne opisywały ten sam bieżący system.

Dlatego spójność dokumentacji jest traktowana jako część procesu inżynieryjnego, a nie jako coś dodanego na końcu.

## Obsługiwane systemy

LUMS jest zaprojektowany do zarządzania systemami Linuksa przy użyciu obsługiwanych natywnych menedżerów pakietów.

### Debian / Ubuntu

Obsługiwany stos zarządzania pakietami:

```text
APT
dpkg
```

Klient używa natywnych narzędzi zarządzania pakietami Debiana do:

* inwentarza pakietów
* wykrywania aktualizacji
* wyszukiwania pakietów
* instalacji pakietów
* usuwania pakietów
* aktualizacji pakietów
* aktualizacji systemu

### Arch Linux

Obsługiwany stos zarządzania pakietami:

```text
pacman
```

Klient używa natywnych narzędzi zarządzania pakietami Arch do:

* inwentarza pakietów
* wykrywania aktualizacji
* wyszukiwania pakietów
* instalacji pakietów
* usuwania pakietów
* aktualizacji pakietów
* aktualizacji systemu

---

## Wymagania klienta

Zarządzany klient Linuksa wymaga:

* obsługiwanej dystrybucji Linuksa
* agenta LUMS
* łączności sieciowej z serwerem LUMS
* zarejestrowanego tokena klienta
* działającego natywnego menedżera pakietów
* systemd dla komponentów wykonawczych opartych na timerach/usługach

Klient nie wymaga, aby serwer LUMS miał bezpośredni dostęp do jego bazy danych pakietów.

Klient wykonuje lokalne operacje na pakietach i raportuje wyniki do serwera.

---

## Stos technologiczny

### Serwer

* Python
* Flask
* Gunicorn
* SQLite
* HTML
* CSS
* JavaScript
* Nginx
* Docker

### Uwierzytelnianie i bezpieczeństwo

* hashowanie haseł Argon2
* sesje po stronie serwera
* ochrona CSRF
* szablony ról z uprawnieniami dla poszczególnych użytkowników
* skróty tokenów klientów SHA-256
* HTTPS
* rejestrowanie audytu

### Klient

* Python
* systemd
* APT / dpkg
* pacman
* `loginctl` tam, gdzie dostępne są informacje o stanie bezczynności

---

## Struktura projektu

Repozytorium jest zorganizowane w oddzielne komponenty serwera, klienta, frontendu i testów.

Uproszczona struktura to:

```text id="1rq7v7"
LUMS/
├── agent/
│   ├── agent.py
│   └── package_manager.py
│
├── server/
│   ├── app.py
│   ├── migrations/
│   ├── static/
│   ├── templates/
│   └── ...
│
├── tests/
│   ├── test_rbac.py
│   ├── test_package_search.py
│   ├── test_job_result.py
│   └── ...
│
├── Dockerfile
├── docker-entrypoint.sh
├── .dockerignore
├── .gitignore
└── documentation
```

Dokładny układ repozytorium może ewoluować w miarę rozwoju LUMS.

Rozdzielenie architektoniczne pomiędzy serwerem, agentem, abstrakcją menedżera pakietów, frontendem i testami jest celowe.

---

## Aplikacja serwera

Aplikacja Flask zapewnia centralne API LUMS i interfejs webowy.

Jej obowiązki obejmują:

* uwierzytelnianie
* autoryzację
* obsługę sesji
* zarządzanie klientami
* zarządzanie użytkownikami
* inwentarz oprogramowania
* inwentarz aktualizacji
* wyszukiwanie pakietów
* zadania aktualizacji
* obsługę wyników zadań
* rejestrowanie audytu
* trwałość bazy danych

Aplikacja jest obsługiwana przez Gunicorn wewnątrz kontenera.

Nginx zapewnia zewnętrzny punkt wejścia HTTPS.

---

## Agent

Agent LUMS jest instalowany bezpośrednio na zarządzanych klientach Linuksa.

Obecna wersja agenta:

```text id="w8p4wz"
1.7.0
```

Agent odpowiada za część łańcucha wykonania LUMS po stronie klienta.

Jego obowiązki obejmują:

* raportowanie stanu klienta
* zbieranie zainstalowanego oprogramowania
* wykrywanie dostępnych aktualizacji
* wyszukiwanie pakietów
* wykonywanie operacji na pakietach
* raportowanie wyników zadań
* wykrywanie wymagań restartu
* obsługę informacji o stanie bezczynności
* uczestnictwo we wznawianiu zadań

Agent nie zapewnia nieograniczonej zdalnej powłoki.

---

## Warstwa menedżera pakietów

Implementacja menedżera pakietów izoluje zachowanie specyficzne dla dystrybucji od reszty agenta.

Koncepcyjnie:

```text id="zq8xq3"
Agent
  │
  ▼
Package Manager Interface
  │
  ├── Debian / Ubuntu
  │      └── APT / dpkg
  │
  └── Arch Linux
         └── pacman
```

Pozwala to systemowi zadań aktualizacji wyższego poziomu pracować ze strukturalnymi operacjami bez potrzeby znajomości każdego polecenia specyficznego dla dystrybucji.

---

## Watcher

Watcher wykonania LUMS monitoruje zadania, które mają zostać wykonane na kliencie.

Obecna wersja watchera:

```text id="7k6w3s"
1.2.1
```

Watcher działa razem z agentem i stanem zadań po stronie serwera.

Ta architektura pozwala LUMS wykrywać sytuacje wykonawcze, w których zadanie pozostaje oczekujące lub w inny sposób wymaga uwagi.

---

## Integracja z systemd

Klient używa systemd do planowanego i kontrolowanego wykonania.

Odpowiednie komponenty obejmują jednostki usług i timerów dla:

* raportowania klienta
* wykrywania aktualizacji
* wykonania/monitorowania zadań

Zapewnia to przewidywalne wykonanie bez wymogu stale działającego procesu pierwszoplanowego dla każdej operacji okresowej.

Agent klienta może być również uruchamiany ręcznie podczas instalacji i rozwiązywania problemów.

---

## Wykonanie uwzględniające bezczynność

Wykonanie uwzględniające bezczynność ma na celu zmniejszenie zakłóceń dla aktywnych użytkowników.

Obecny próg bezczynności to:

```text id="g8v0lq"
300 seconds
```

Klient określa stan bezczynności przy użyciu dostępnych informacji o sesji lokalnej.

Tam, gdzie jest to obsługiwane, używany jest `loginctl`.

Agent rozróżnia pomiędzy:

```text id="6v3m4k"
confirmed idle
active
idle state unavailable
```

Niedostępny stan bezczynności nie jest po cichu interpretowany jako bezczynność.

To sprawia, że decyzja o wykonaniu jest jawna i diagnozowalna.

---

## Cykl życia zadania aktualizacji

Kompletny cykl życia zadania aktualizacji można przedstawić jako:

```text id="h4d9kv"
Create
  │
  ▼
Validate
  │
  ▼
Persist
  │
  ▼
Claim
  │
  ▼
Execute
  │
  ├──────────────► SUCCESS
  │
  ├──────────────► FAILED
  │
  └──────────────► RECOVERY
                         │
                         ▼
                      Execute
```

Zadanie jest utrwalane przed wykonaniem.

Oznacza to, że serwer zachowuje wiedzę o zamierzonej operacji, nawet jeśli klient lub aplikacja zostaną przerwane.

---

## Typy zadań

LUMS obecnie obsługuje strukturalne akcje aktualizacji, w tym:

```text id="v7r1f8"
INSTALL_PACKAGE
REMOVE_PACKAGE
UPDATE_PACKAGE
UPDATE_SYSTEM
```

Te akcje są celowo ograniczone.

LUMS to system zarządzania aktualizacjami, a nie ogólny framework zdalnego wykonywania poleceń.

---

## Stan zadania na poziomie pakietów

Zadania zawierające wiele pakietów mogą śledzić postęp na poziomie pakietów.

Na przykład:

```text id="v9w1sh"
Job #42

package-a → SUCCESS
package-b → SUCCESS
package-c → FAILED
package-d → PENDING
```

Dlatego wznawianie może działać na nieukończonych częściach zadania, a nie bezmyślnie powtarzać pomyślne operacje na pakietach.

---

## Wznawianie zadań

Wznawianie jest zaprojektowane wokół trwałych punktów kontrolnych.

Serwer utrzymuje stan zadania.

Klient raportuje wyniki na poziomie pakietów.

Jeśli wykonanie zostanie przerwane, serwer może określić, która praca została już wykonana, a która pozostaje kwalifikująca się do wznowienia.

Zamierzona zasada wznawiania to:

> **Kontynuuj od znanego stanu, zamiast zakładać, że nic się nie stało.**

---

## Walidacja wyników

Wyniki zadań klienta są walidowane przed przyjęciem do trwałego stanu serwera.

Chroni to stan zadania przed źle sformułowanymi lub niekompletnymi zgłoszeniami wyników.

Walidacja jest stosowana do odpowiednich pól, takich jak:

* tożsamość zadania
* stan wykonania
* dane wyników pakietów
* informacje o błędach
* informacje o restarcie

Dlatego warstwa przetwarzania wyników działa jako kolejna granica pomiędzy uwierzytelnionym klientem a trwałym stanem serwera.

---

## Zarządzanie użytkownikami

Zarządzanie użytkownikami wymaga uprawnienia `users.manage`.

Autoryzowani użytkownicy mogą tworzyć użytkowników z szablonu roli i dostosowywać indywidualne uprawnienia przypisane do każdego konta.

Obecne role to:

```text id="2xqv79"
Administrator
Operator
Viewer
```

Działania zarządzania użytkownikami są uwierzytelniane, sprawdzane pod kątem uprawnień, walidowane, chronione przed CSRF, gdy ma to zastosowanie, i rejestrowane w ścieżce audytu.

---

## Zarządzanie klientami

Administratorzy mogą zarządzać zarejestrowanymi klientami.

Funkcje zarządzania klientami obejmują:

* rejestrację
* wyłączanie
* rotację tokenów
* sprawdzanie stanu klienta

Uwierzytelnianie klienta jest niezależne dla każdego zarejestrowanego klienta.

Wyłączenie klienta uniemożliwia mu kontynuowanie normalnej uwierzytelnionej komunikacji z serwerem.

---

## Historia aktualizacji

LUMS utrzymuje trwały stan zadań aktualizacji, dzięki czemu zakończone i nieudane operacje pozostają widoczne po wykonaniu.

Autoryzowani użytkownicy mogą przeglądać historię operacji aktualizacji zgodnie ze swoją rolą.

Historia ma zapewniać kontekst operacyjny, a nie tylko pokazywać najnowszy inwentarz pakietów.

---

## Audytowalność

LUMS utrzymuje dwie powiązane, ale odrębne formy informacji operacyjnych:

### Dzienniki aplikacji

Używane głównie do:

* diagnostyki
* błędów
* zachowania środowiska wykonawczego
* rozwiązywania problemów

### Dzienniki audytu

Używane głównie do:

* działań administracyjnych
* zdarzeń istotnych dla bezpieczeństwa
* zmian ważnego stanu
* rozliczalności

Utrzymywanie tych pojęć oddzielnie ułatwia rozwiązywanie problemów i przegląd administracyjny.

---

## Strategia testowania

Zestaw testów LUMS obejmuje wiele warstw aplikacji.

### Uwierzytelnianie

Testy obejmują zachowanie uwierzytelniania, obsługę sesji i kontrole bezpieczeństwa.

### RBAC

Testy weryfikują, że:

* Administratorzy mogą wykonywać działania administracyjne
* Operatorzy otrzymują swoje dozwolone funkcje zarządzania
* Viewerzy pozostają tylko do odczytu

### Zarządzanie pakietami

Testy obejmują zachowanie wyszukiwania pakietów i obsługę API związaną z zarządzaniem pakietami.

### Zadania aktualizacji

Testy obejmują:

* tworzenie zadań
* walidację
* przejścia stanów
* obsługę wyników
* zachowanie wznawiania

### Bezpieczeństwo

Testy obejmują zachowanie aplikacji wrażliwe na bezpieczeństwo i przypadki regresji.

### Pełny zestaw

Uruchom pełny zestaw testów z katalogu głównego repozytorium:

```bash
./.venv-test/bin/pytest -q
```

Liczba testów zmienia się w miarę rozwoju projektu; polegaj na wyniku polecenia, a nie na stałej liczbie wydrukowanej w tym dokumencie.

---

## Ciągła integracja

Projekt używa ciągłej integracji do uruchamiania automatycznych kontroli względem zmian.

Potok CI pomaga wykrywać regresje, zanim zmiany zostaną uznane za gotowe do wydania.

Dlatego przepływ pracy rozwojowej to:

```text id="v3n9k8"
Change
  ↓
Test
  ↓
Security Review
  ↓
Documentation Review
  ↓
CI
  ↓
Release Preparation
```

Pomyślne uruchomienie CI nie zastępuje ręcznego przeglądu bezpieczeństwa ani dokumentacji.

---

## Dokumentacja

LUMS utrzymuje oddzielną dokumentację dla różnych zagadnień operacyjnych.

### `README.md`

Przegląd projektu, architektura, funkcje, podstawa bezpieczeństwa, status rozwoju i kierunek projektu.

### `install.md`

Procedury instalacji, wdrażania, konfiguracji klienta, walidacji, aktualizacji i usuwania.

### `administration.md`

Rutynowa administracja, konserwacja, kopie zapasowe, aktualizacje, procedury operacyjne i administracja awaryjna.

### `security.md`

Architektura bezpieczeństwa, kontrole bezpieczeństwa, wyniki audytu, utwardzanie i informacje o bezpieczeństwie gotowości wydania.

### `troubleshooting.md`

Procedury diagnostyczne dla problemów z serwerem, klientem, zadaniami, zarządzaniem pakietami, uwierzytelnianiem, bazą danych, kontenerem i siecią.

### `LUMS_Optional_Theme_System.md`

Architektura i wskazówki konserwacji dla opcjonalnych motywów frontendu LUMS.

Dokumentacja jest celowo podzielona według odpowiedzialności, aby instrukcje operacyjne nie mieszały się z projektem bezpieczeństwa ani dostosowaniem wizualnym.

---

## Zasada dokumentacji

Dokumentacja jest traktowana jako część systemu.

Funkcja nie jest uważana za całkowicie ukończoną, gdy kod działa, ale dokumentacja nadal opisuje starszą architekturę.

Zamierzona relacja to:

```text id="0m1m5u"
Implementation
      │
      ├── Tests
      ├── Security Review
      └── Documentation
               │
               ▼
          Release Ready
```

Jest to szczególnie ważne dla wrażliwych na bezpieczeństwo procedur wdrażania i administracji.

## Obecny status

LUMS to aktywnie rozwijana platforma zarządzania aktualizacjami Linuksa.

Obecna implementacja obejmuje:

* scentralizowane zarządzanie klientami
* inwentarz oprogramowania
* wykrywanie aktualizacji
* wyszukiwanie pakietów
* instalację i usuwanie pakietów
* aktualizacje konkretnych pakietów
* aktualizacje systemu
* trwałe zadania aktualizacji
* stan zadań na poziomie pakietów
* wznawianie zadań
* wykrywanie restartu
* wykonanie uwzględniające bezczynność
* uwierzytelnianie tokenem klienta
* rotację tokenów
* uwierzytelnianie administracyjne
* kontrolę dostępu opartą na rolach
* zarządzanie użytkownikami
* rejestrowanie audytu
* utwardzanie kontenera
* transport HTTPS
* testy automatyczne
* ciągłą integrację

Projekt znajduje się obecnie w końcowej fazie dokumentacji i gotowości wydania.

---

## Status bezpieczeństwa

Główne obszary przeglądu bezpieczeństwa zostały zaimplementowane i przejrzane.

Obecna podstawa bezpieczeństwa obejmuje:

```text
Authentication
    ├── Argon2 password hashing
    ├── session handling
    ├── session revocation
    └── login rate limiting

Authorization
    ├── Administrator
    ├── Operator
    └── Viewer

Client Security
    ├── per-client tokens
    ├── SHA-256 token digests
    └── token rotation

API Security
    ├── input validation
    ├── CSRF protection
    ├── RBAC enforcement
    └── parameterized SQL

Runtime Security
    ├── non-root container
    ├── read-only root filesystem
    ├── dropped capabilities
    ├── no-new-privileges
    ├── restricted temporary filesystems
    └── protected secret mount

Network Security
    ├── HTTPS
    ├── reverse proxy
    ├── loopback application binding
    └── firewall restrictions
```

Bezpieczeństwo jest traktowane jako ciągła odpowiedzialność inżynierska, a nie jednorazowa lista kontrolna.

---

## Status wydania

LUMS nie rości sobie obecnie stabilnej wersji produkcyjnej.

Obecnie nie ma:

* końcowej wersji semantycznej
* stabilnego tagu wydania
* GitHub Release

Projekt celowo podąża za sekwencją wydania:

```text id="f3c4y9"
Implementation
      ↓
Security Review
      ↓
Documentation Review
      ↓
Full Test Suite
      ↓
CI
      ↓
Version Assignment
      ↓
Git Tag
      ↓
GitHub Release
```

Pierwsze oficjalne wydanie powinno zostać utworzone dopiero po uznaniu bieżącej implementacji, przeglądu bezpieczeństwa, dokumentacji i testów regresji za ukończone.

---

## Plan rozwoju

Plan rozwoju jest celowo skoncentrowany na stabilności i łatwości utrzymania, a nie na dodawaniu funkcji bez ukończenia istniejących podstaw.

### Obecna faza

* ukończyć przegląd dokumentacji
* usunąć pozostałe niespójności dokumentacji
* zamknąć pracę audytu dokumentacji
* wykonać końcowe pełne uruchomienie testów
* zweryfikować CI
* przygotować wersję wydania
* utworzyć pierwszy oficjalny tag Git
* opublikować pierwszy GitHub Release

### Przyszły rozwój

Potencjalna przyszła praca może obejmować:

* dodatkowe dystrybucje Linuksa
* dodatkowe backendy menedżerów pakietów
* dalsze ulepszenia UI
* dodatkowe możliwości raportowania
* rozszerzoną automatyzację operacyjną
* dodatkowe kontrole bezpieczeństwa
* dalsze pokrycie testami

Przyszłe funkcje powinny zachować istniejące granice architektoniczne.

---

## Czym LUMS nie jest

LUMS celowo nie jest zaprojektowany jako:

* ogólna zdalna powłoka
* zamiennik APT, dpkg lub pacman
* pełna platforma zarządzania konfiguracją
* zestaw do zarządzania punktami końcowymi dla każdego systemu operacyjnego
* usługa wyłącznie chmurowa
* niekontrolowany framework wykonywania poleceń

LUMS skupia się na węższym problemie:

> **Kontrolowane zarządzanie oprogramowaniem i aktualizacjami Linuksa z trwałym stanem i audytowalnością.**

---

## Filozofia rozwoju

LUMS kieruje się prostym cyklem rozwoju:

```text id="8a0mve"
Build
  ↓
Test
  ↓
Secure
  ↓
Document
```

Funkcja nie jest uważana za ukończoną tylko dlatego, że działa w środowisku programisty.

Powinna być również:

* przetestowana
* przejrzana pod kątem bezpieczeństwa
* udokumentowana
* powtarzalna
* zrozumiała
* odtwarzalna, gdy ma to zastosowanie

---

## Filozofia zmian

Zmiany powinny być dokonywane świadomie.

Typowa zmiana powinna odpowiadać na pytania:

1. Jaki problem to rozwiązuje?
2. Który komponent powinien być właścicielem zmiany?
3. Czy zmiana wpływa na bezpieczeństwo?
4. Czy wpływa na trwały stan?
5. Czy wpływa na klientów?
6. Czy wymaga zmian w dokumentacji?
7. Które testy dowodzą, że istniejąca funkcjonalność nadal działa?

Zmniejsza to ryzyko naprawy jednej części systemu przy jednoczesnym cichym zepsuciu innej.

---

## Przepływ pracy rozwojowej

Preferowany przepływ pracy rozwojowej to:

```text id="r8u6o1"
Understand
   ↓
Implement
   ↓
Test
   ↓
Inspect
   ↓
Harden
   ↓
Document
   ↓
Regression Test
```

Zmiany wrażliwe na bezpieczeństwo otrzymują dodatkową weryfikację przed uznaniem za ukończone.

---

## Repozytorium

Repozytorium projektu jest hostowane na GitHub:

**NovaForgeCtrl/LUMS**

Repozytorium zawiera kod źródłowy aplikacji, komponenty klienta, testy, konfigurację kontenera i dokumentację projektu.

---

## Zestaw dokumentacji

Obecny zestaw dokumentacji składa się z:

```text id="0xw7cy"
README.md
install.md
administration.md
security.md
troubleshooting.md
LUMS_Optional_Theme_System.md
```

Każdy dokument ma określony cel.

README zapewnia przegląd na poziomie projektu.

Przewodnik instalacji wyjaśnia wdrażanie.

Przewodnik administracji wyjaśnia bieżące działanie.

Przewodnik bezpieczeństwa dokumentuje architekturę bezpieczeństwa i stan audytu.

Przewodnik rozwiązywania problemów zapewnia procedury diagnostyczne.

Dokument opcjonalnych motywów obejmuje architekturę motywów frontendu.

---

## Licencja

LUMS jest wydany na licencji MIT.

Licencja ma na celu utrzymanie projektu otwartym i dostępnym, jednocześnie pozwalając na używanie, modyfikację i redystrybucję na warunkach licencji.

Pełny tekst prawny znajduje się w pliku licencji repozytorium.

---

## Społeczność i wkład

LUMS to projekt open source, a wkład jest mile widziany.

Przydatny wkład może obejmować:

* raporty błędów
* raporty bezpieczeństwa
* ulepszenia dokumentacji
* testy
* obsługę menedżerów pakietów
* ulepszenia frontendu
* ulepszenia backendu
* ulepszenia wdrażania

Wkład powinien zachować zasady architektoniczne i bezpieczeństwa projektu.

---

## Raporty bezpieczeństwa

Problemy bezpieczeństwa nie powinny być traktowane jak zwykłe prośby o funkcje.

Zgłaszając problem bezpieczeństwa, podaj wystarczająco dużo informacji, aby odtworzyć i zrozumieć problem bez niepotrzebnego ujawniania wrażliwych informacji.

Zmiany związane z bezpieczeństwem powinny zostać starannie przejrzane przed scaleniem.

---

## Tożsamość projektu

LUMS jest zbudowany wokół prostej idei:

> **Zarządzanie aktualizacjami Linuksa bez zbędnego szumu.**

Projekt nie próbuje ukryć złożoności, udając, że zarządzanie pakietami Linuksa jest proste.

Zamiast tego sprawia, że istotny stan jest widoczny:

```text id="q2j5r0"
What is installed?
        ↓
What can be updated?
        ↓
What should change?
        ↓
Who requested it?
        ↓
What actually happened?
        ↓
What state remains?
```

Te informacje są podstawą kontrolowanego zarządzania aktualizacjami.

---

## Architektura końcowa

Na najwyższym poziomie LUMS można rozumieć jako pięć warstw:

```text id="7b4p6n"
┌───────────────────────────────────────────────┐
│                    UI                         │
│       Human interaction and visibility        │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                    API                        │
│    Authentication, authorization, validation  │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                  Persistence                   │
│       Jobs, clients, users, results, audit   │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                    Agent                      │
│      Local execution and system reporting     │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│              Native Linux Tools               │
│              APT / dpkg / pacman             │
└───────────────────────────────────────────────┘
```

Każda warstwa ma określoną odpowiedzialność.

UI zapewnia interakcję.

API egzekwuje politykę.

SQLite zapewnia trwały stan.

Agent wykonuje kontrolowane działanie po stronie klienta.

Natywny menedżer pakietów dokonuje rzeczywistej zmiany systemu.

---

## Zasada końcowa

LUMS jest zbudowany wokół jednej centralnej zasady:

> **Obserwuj system. Kontroluj zmianę. Rejestruj wynik.**

Ta zasada dotyczy architektury oprogramowania, wykonania aktualizacji, modelu bezpieczeństwa, mechanizmów wznawiania i dokumentacji.

**Zarządzanie aktualizacjami Linuksa bez zbędnego szumu.**
