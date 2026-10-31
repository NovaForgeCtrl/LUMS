# LUMS — Opcjonalny system motywów

> **Jeden LUMS · wiele interfejsów · ten sam backend**

LUMS udostępnia opcjonalny system motywów po stronie klienta, który pozwala zmieniać wygląd interfejsu bez zmiany podstawowych funkcji LUMS.

Motywy są wyłącznie warstwą prezentacji. Nie zastępują, nie modyfikują ani nie omijają backendu LUMS, uwierzytelniania, autoryzacji, wykonywania aktualizacji, zarządzania pakietami, zarządzania klientami, obsługi zadań ani mechanizmów bezpieczeństwa.

System motywów pozwala dostosować LUMS do różnych preferencji wizualnych, zachowując spójność samej aplikacji.

## Stan implementacji i źródło prawdy

Obecna implementacja przeglądarkowa znajduje się w `server/static/theme.js`.
Obsługuje motywy `standard`, `LUMSStadium`, `golf`, `nerd`, `geek` i `admin`;
zapisuje wybór w `localStorage` przeglądarki pod kluczem `lums-theme`; i wraca
do `standard`, gdy zapisanego identyfikatora brakuje lub jest nieprawidłowy.
Motyw `nerd` uruchamia efekt Matrix, a `geek` — efekt sieci. Wybór motywu jest
preferencją przeglądarki, a nie ustawieniem konta ani stanem autoryzacji serwera.

Ten dokument zawiera również wymagania projektowe i przykłady koncepcyjne.
Stwierdzenia używające określeń takich jak „powinien”, „musi” lub „przyszły”
opisują wytyczne architektoniczne; nie dowodzą, że konkretna funkcja wizualna
lub dostępności jest zaimplementowana. Przed uznaniem koncepcji za dostępną
funkcję sprawdź bieżące zachowanie w kodzie źródłowym.

---

## 1. Przegląd

Opcjonalny system motywów pozwala interfejsowi webowemu LUMS oferować różne środowiska wizualne przy użyciu tego samego backendu aplikacji.

Motyw może zmieniać:

* kolory
* typografię
* tła
* elementy dekoracyjne
* akcenty wizualne
* wygląd nawigacji
* animacje
* opcjonalne efekty wizualne
* prezentację konkretnej strony

Motyw nie może zmieniać:

* uprawnień użytkowników
* dostępnych endpointów API
* sposobu uwierzytelniania
* decyzji autoryzacyjnych
* ochrony CSRF
* uwierzytelniania klientów
* wykonywania aktualizacji
* uprawnień do zarządzania pakietami
* obsługi stanu zadań
* rejestrowania audytu
* działania bazy danych
* granic bezpieczeństwa

Zasada jest prosta:

> **Motywy zmieniają wygląd LUMS, a nie to, co LUMS może robić.**

---

## 2. Zasady projektowe

System motywów opiera się na kilku zasadach.

### 2.1 Opcjonalność

Motywy są opcjonalną funkcją frontendu.

LUMS pozostaje w pełni funkcjonalny bez wybierania dodatkowego motywu.

Standardowy wygląd LUMS jest domyślną prezentacją.

### 2.2 Po stronie klienta

Wybór motywu należy do frontendu.

Zmiana motywu nie może wymagać zmian stanu aplikacji po stronie serwera.

Wybrany motyw jest więc preferencją prezentacji, a nie uprawnieniem konta ani konfiguracją backendu.

### 2.3 Niezależność od backendu

Wszystkie motywy korzystają z tego samego backendu LUMS.

Poniższe elementy pozostają niezależne od wybranego motywu:

```text
Authentication
Authorization
RBAC
Client Management
Software Inventory
Update Detection
Package Management
Update Jobs
Job Recovery
Audit Logging
Database Operations
```

Backend pozostaje autorytatywnym źródłem dla wszystkich decyzji istotnych dla bezpieczeństwa i działania systemu.

### 2.4 Motyw nie zapewnia bezpieczeństwa

Motywu nigdy nie wolno używać jako mechanizmu bezpieczeństwa.

Na przykład ukrycie działania w interfejsie nie nadaje ani nie odbiera uprawnień.

Jeśli użytkownik nie może wykonać operacji, serwer musi ją odrzucić niezależnie od aktywnego motywu.

Dzięki temu prezentacja frontendu nie stanie się granicą autoryzacji.

### 2.5 Bezpieczne rozwiązanie zastępcze

System motywów powinien zawsze zapewniać prawidłowe rozwiązanie zastępcze.

Jeśli motyw nie został wybrany, zapisany motyw nie jest już dostępny, identyfikator motywu jest nieprawidłowy albo nie można załadować jego zasobu, LUMS powinien wrócić do standardowej prezentacji zamiast pozostawiać interfejs bezużytecznym.

---

## 3. Architektura koncepcyjna

System motywów można postrzegać jako osobną warstwę prezentacji otaczającą istniejącą aplikację LUMS.

```text
┌──────────────────────────────────────┐
│              LUMS UI                 │
│                                      │
│  ┌────────────────────────────────┐  │
│  │        Theme Presentation      │  │
│  │                                │  │
│  │ Standard / Stadium / Golf /    │  │
│  │ Nerd / Geek / Admin / ...      │  │
│  └────────────────────────────────┘  │
│                  │                   │
│                  ▼                   │
│        Common Frontend Logic        │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│             LUMS API                 │
│                                      │
│ Authentication / RBAC / Jobs /       │
│ Clients / Packages / Updates / Logs  │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│          LUMS Backend                │
│                                      │
│ Flask / SQLite / Job Processing /   │
│ Client Communication                 │
└──────────────────────────────────────┘
```

Ważna granica oddziela **prezentację** od **logiki aplikacji**.

Motywy należą nad tą granicą.

---

## 4. Cykl życia motywu

Koncepcyjnie wybór motywu przebiega następująco:

```text
User selects theme
        │
        ▼
Frontend stores selection
        │
        ▼
Theme initialization
        │
        ▼
Theme applied to UI
        │
        ▼
LUMS continues using
the same backend and permissions
```

Sam wybór nie tworzy nowego środowiska LUMS.

Nadal istnieje tylko jedna aplikacja LUMS, jeden backend i jeden model bezpieczeństwa.

---

## 5. Identyfikatory motywów

Motywy powinny używać stabilnych identyfikatorów wewnętrznych zamiast nazw wyświetlanych.

Na przykład:

```text
standard
LUMSStadium
golf
nerd
geek
admin
```

Identyfikator jest szczegółem implementacji.

Widoczną nazwę motywu można zmienić niezależnie, bez zmieniania backendu ani architektury aplikacji.

Po usunięciu lub zmianie nazwy identyfikatora system powinien zapewnić rozwiązanie zastępcze użytkownikom, którzy nadal mają lokalnie zapisany poprzedni identyfikator.

---

## 6. Rozdzielenie odpowiedzialności

System motywów ma celowo wąski zakres odpowiedzialności.

### Warstwa motywów

Odpowiada za:

* prezentację wizualną
* wybór motywu
* style właściwe dla motywu
* opcjonalne efekty wizualne
* dekoracje frontendu właściwe dla motywu
* zachowanie prezentacji związane z dostępnością

### Wspólny frontend

Odpowiada za:

* wyświetlanie danych aplikacji
* wywoływanie API LUMS
* renderowanie zadań i informacji o oprogramowaniu
* obsługę interakcji użytkownika
* stosowanie reguł widoczności na poziomie prezentacji

### Backend

Odpowiada za:

* uwierzytelnianie
* autoryzację
* RBAC
* ochronę CSRF
* uwierzytelnianie klientów
* tworzenie zadań
* wykonywanie zadań
* zarządzanie pakietami
* operacje na bazie danych
* rejestrowanie audytu
* decyzje dotyczące bezpieczeństwa

Ten podział ma fundamentalne znaczenie dla projektu.

---

## 7. Granica bezpieczeństwa

System motywów **nie jest zaufanym kodem do celów autoryzacji**.

Nawet jeśli motyw zmienia lub ukrywa element interfejsu, backend nadal odpowiada za weryfikację żądanej operacji.

Koncepcyjnie:

```text
Frontend visibility
        ≠
Backend permission
```

Na przykład:

```text
Viewer
  │
  ├── Theme may display no package-management controls
  │
  └── Backend still rejects unauthorized package operations
```

Ta sama zasada dotyczy funkcji administracyjnych, zadań aktualizacji, zarządzania klientami i każdej innej uprzywilejowanej operacji.

---

## 8. Zasada operacyjna

System motywów powinien pozostawać niewidoczny dla architektury operacyjnej LUMS.

Zmiana motywu nie może wymagać:

* przebudowy bazy danych
* zmiany konfiguracji klientów
* zmiany tokenów klientów
* restartu agentów aktualizacji
* zmiany zadań aktualizacji
* modyfikacji RBAC
* zmiany konfiguracji sieci
* zmiany sposobu zarządzania pakietami

Motyw jest preferencją prezentacji, a nie konfiguracją operacyjną.

---

## 9. Zakres dokumentacji

Ten dokument opisuje opcjonalny system motywów LUMS.

Ogólne zagadnienia dotyczące LUMS są opisane osobno:

* instalacja i wdrażanie → `install.md`
* administracja i utrzymanie → `administration.md`
* rozwiązywanie problemów → `troubleshooting.md`
* architektura bezpieczeństwa i audyty → `security.md`
* ogólny opis projektu → `README.md`

Rozdzielenie tych obowiązków zapobiega przekształceniu dokumentacji motywów w drugi podręcznik instalacji lub administracji.

---

## 10. Podstawowa zasada

Opcjonalny system motywów można podsumować następująco:

> **Jeden LUMS. Jeden backend. Jeden model bezpieczeństwa. Wiele możliwych interfejsów.**

# LUMS — Opcjonalny system motywów

## Część 2 — Struktura i wybór motywów

## 11. Struktura motywu

Opcjonalny system motywów oddziela wybór motywu od właściwej prezentacji wizualnej.

Koncepcyjnie motyw składa się z trzech warstw:

```text
Theme Identifier
       │
       ▼
Theme Selection
       │
       ▼
Theme Presentation
```

Identyfikator określa, który motyw został wybrany.

Mechanizm wyboru określa, który motyw powinien być obecnie aktywny.

Warstwa prezentacji stosuje odpowiednią konfigurację wizualną interfejsu LUMS.

Taki podział pozwala dodawać i usuwać motywy bez zmiany podstawowej architektury aplikacji LUMS.

---

## 12. Wybór motywu

Wyborem motywu zarządza frontend.

Wybrany motyw jest traktowany jako lokalna preferencja prezentacji, a nie właściwość konta po stronie serwera.

Koncepcyjnie:

```text
User
 │
 ▼
Theme Selector
 │
 ▼
Selected Theme Identifier
 │
 ▼
Frontend Theme Initialization
 │
 ▼
Active Theme
```

Backend nie musi wiedzieć, który motyw wizualny jest aktualnie wybrany.

Zmiana motywu nie wpływa więc na innych użytkowników.

Dwóch użytkowników może korzystać z tej samej instancji LUMS, używając zupełnie różnych motywów wizualnych.

---

## 13. Lokalna preferencja motywu

Wybrany motyw może być zapisywany lokalnie przez przeglądarkę.

Lokalny zapis zapewnia wygodę:

```text
Browser
   │
   ├── Theme preference
   │
   └── LUMS application
```

Zapisany wybór motywu należy traktować jako niezaufany stan po stronie klienta.

Serwerowi nigdy nie wolno interpretować go jako:

* roli
* uprawnienia
* stanu uwierzytelnienia
* ustawienia bezpieczeństwa
* preferencji administracyjnej

Przeglądarka może wybrać wygląd, ale nie kontroluje autoryzacji.

---

## 14. Inicjalizacja motywu

Po załadowaniu interfejsu LUMS frontend ustala, który motyw ma być aktywny.

Koncepcyjna sekwencja:

```text
Page Load
   │
   ▼
Read Stored Theme
   │
   ▼
Is Theme Valid?
   │
   ├── Yes ──────► Apply Theme
   │
   └── No ───────► Use Standard Theme
```

Jeśli nie ma zapisanej preferencji, należy użyć standardowej prezentacji LUMS.

Jeśli zapisany identyfikator nie jest już obsługiwany, należy zastosować to samo rozwiązanie zastępcze.

Zapobiega to uszkodzeniu interfejsu przez nieaktualną preferencję lokalną.

---

## 15. Motyw domyślny

Standardowy motyw LUMS jest podstawową prezentacją.

Stanowi punkt odniesienia dla opcjonalnych motywów.

Dlatego standardowy motyw powinien pozostać:

* funkcjonalny
* czytelny
* dostępny
* kompletny wizualnie
* niezależny od opcjonalnych zasobów dekoracyjnych

Opcjonalne motywy nie mogą stać się warunkiem normalnego działania LUMS.

---

## 16. Zastosowanie motywu

Frontend może reprezentować aktywny motyw za pomocą współdzielonego stanu aplikacji albo atrybutu motywu na elemencie głównym.

Koncepcyjnie:

```html
<html data-theme="theme-id">
```

Dokładna implementacja może się zmieniać wraz z rozwojem frontendu.

Ważnym wymaganiem architektonicznym jest spójna identyfikacja aktywnego motywu przez system stylów frontendu.

Pozwala to oddzielić style właściwe dla motywu od wspólnej struktury aplikacji.

---

## 17. Style właściwe dla motywu

Style motywów powinny być implementowane głównie za pomocą CSS, a nie przez powielanie znaczników aplikacji.

Koncepcyjnie:

```text
Common HTML
     │
     ├── Standard styling
     ├── Stadium styling
     ├── Golf styling
     ├── Nerd styling
     ├── Geek styling
     └── Admin styling
```

Dzięki temu te same komponenty aplikacji pozostają dostępne we wszystkich motywach.

Na przykład tabela klientów nadal jest tabelą klientów niezależnie od aktywnego motywu.

Zmienia się wyłącznie jej prezentacja.

---

## 18. Współdzielone komponenty aplikacji

Motywy nie powinny tworzyć osobnych wersji stron LUMS.

Należy zachować następującą zasadę:

```text
One component
       │
       ├── Theme A
       ├── Theme B
       ├── Theme C
       └── Theme D
```

Zamiast:

```text
Theme A → separate page
Theme B → separate page
Theme C → separate page
```

Powielanie stron znacznie utrudniałoby utrzymanie i mogłoby prowadzić do różnic w działaniu między motywami.

Motyw powinien więc ozdabiać wspólny interfejs, a nie zastępować samą aplikację.

---

## 19. Zasoby motywów

W odpowiednich przypadkach motywy mogą korzystać z dodatkowych zasobów frontendu.

Możliwe zasoby:

* obrazy tła
* grafiki dekoracyjne
* ikony
* animacje
* nakładki wizualne
* ilustracje właściwe dla motywu

Zasoby pozostają częścią warstwy prezentacji frontendu.

Nie mogą zawierać:

* danych uwierzytelniających
* tokenów klientów
* kluczy tajnych
* plików bazy danych
* materiałów uwierzytelniających
* prywatnych danych operacyjnych

Zasoby motywów należy traktować jako publiczne zasoby frontendu.

---

## 20. Opcjonalne efekty wizualne

Niektóre motywy mogą udostępniać dodatkowe efekty wizualne, na przykład:

* animowane tła
* dekoracyjne efekty sieciowe
* ruch otoczenia
* tematyczne elementy interfejsu
* dynamiczne dekoracje wizualne

Efekty te muszą pozostać opcjonalne.

Nie mogą być wymagane do funkcjonalnego działania LUMS.

---

## 21. Ograniczenie ruchu

Efekty wizualne powinny uwzględniać preferencje użytkowników dotyczące ograniczenia ruchu.

Jeśli używane są animowane lub stale zmieniające się elementy, system motywów powinien zapewniać odpowiedni tryb ograniczonego ruchu.

Koncepcyjnie:

```text
Normal motion
     │
     ├── animations enabled
     └── visual effects enabled

Reduced motion
     │
     ├── animations reduced or disabled
     └── essential interface remains functional
```

Dostępność ma pierwszeństwo przed dekoracyjną animacją.

Motyw powinien pozostać użyteczny po wyłączeniu efektów wizualnych.

---

## 22. Niezależność motywów

Zmiana motywu nie może wywoływać skutków ubocznych w działaniu systemu.

Na przykład:

```text
Theme change
     │
     ├── No client restart
     ├── No agent restart
     ├── No job cancellation
     ├── No database migration
     ├── No token rotation
     └── No permission change
```

System motywów jest celowo odizolowany od operacyjnego cyklu życia LUMS.

---

## 23. Obsługa błędów motywu

Motyw powinien bezpiecznie obsługiwać błędy.

Jeśli nie można załadować zasobu lub komponentu prezentacji właściwego dla motywu, wspólny interfejs LUMS powinien pozostać użyteczny.

Preferowana ścieżka odzyskiwania:

```text
Theme error
    │
    ▼
Fallback to standard presentation
    │
    ▼
LUMS remains usable
```

Problem wizualny nie może stać się problemem dostępności aplikacji.

---

## 24. Dodawanie nowego motywu

Nowy motyw powinien zachować istniejący podział między działaniem aplikacji a prezentacją.

Koncepcyjnie:

```text
1. Define theme identifier
2. Define visual design
3. Add theme styling
4. Add optional assets
5. Add theme to selection mechanism
6. Test normal pages
7. Test different RBAC roles
8. Test reduced-motion behavior
9. Test fallback behavior
10. Verify no backend behavior changed
```

Nowy motyw jest ukończony dopiero wtedy, gdy dotychczasowe funkcje LUMS pozostają niezmienione.

---

## 25. Usuwanie motywu

Usuwanie motywu również powinno być obsługiwane w kontrolowany sposób.

Jeśli użytkownik ma lokalnie zapisany usunięty motyw, frontend powinien wykryć, że identyfikator nie jest już dostępny, i wrócić do motywu standardowego.

Usunięcie motywu wizualnego nie może sprawić, że interfejs LUMS użytkownika stanie się bezużyteczny.

---

## 26. Nazewnictwo motywów

Nazwy motywów powinny jasno rozróżniać:

* identyfikator wewnętrzny
* nazwę wyświetlaną
* koncepcję wizualną

Na przykład:

```text
Internal identifier:  standard
Display name:         Standard LUMS
```

Ten podział umożliwia zmianę widocznego tekstu bez niepotrzebnej zmiany implementacji wewnętrznej.

---

## 27. Obecne koncepcje motywów

Opcjonalny system motywów LUMS został zaprojektowany tak, aby oferować wiele tożsamości wizualnych przy zachowaniu wspólnej aplikacji.

Obecnie udokumentowane koncepcje:

| Identyfikator | Koncepcja |
| --- | --- |
| `standard` | Standard LUMS |
| `LUMSStadium` | LUMS Stadium |
| `golf` | Golf Club |
| `nerd` | Nerd Mode |
| `geek` | Geek Lab |
| `admin` | Enterprise Admin |

Motywy te reprezentują różne kierunki wizualne, a nie różne edycje LUMS.

Wszystkie należą do tej samej aplikacji.

---

## 28. Jeden backend, wiele interfejsów

Końcową relację można podsumować następująco:

```text
                     ┌── Standard
                     ├── Stadium
                     ├── Golf
                     ├── Nerd
                     ├── Geek
                     └── Admin
                           │
                           ▼
                    Common LUMS UI
                           │
                           ▼
                       LUMS API
                           │
                           ▼
                     LUMS Backend
```

Warstwa motywów kończy się na granicy prezentacji.

Wszystko poniżej tej granicy jest wspólne dla wszystkich motywów.

# LUMS — Opcjonalny system motywów

## Część 3 — Koncepcje motywów

## 29. Standard LUMS

Motyw Standard LUMS jest referencyjną prezentacją aplikacji.

Ma zapewniać przejrzysty i funkcjonalny interfejs bez wymagania konkretnej koncepcji wizualnej.

Motyw standardowy powinien stawiać na:

* czytelność
* przejrzystą hierarchię informacji
* przewidywalną nawigację
* dostępność
* niewielką liczbę rozpraszających elementów wizualnych
* spójną prezentację komponentów

Jest to motyw zastępczy systemu.

Powinien więc pozostać użyteczny nawet wtedy, gdy żaden opcjonalny motyw wizualny nie jest dostępny.

---

## 30. LUMS Stadium

**LUMS Stadium** to bardziej ekspresyjna interpretacja wizualna interfejsu LUMS.

Koncepcja łączy administrację systemami z tożsamością wizualną inspirowaną stadionem.

Możliwe elementy projektu:

* panele informacyjne inspirowane tablicą wyników
* wyraźniejsze wskaźniki stanu
* prezentacja zorientowana na zdarzenia
* tematyczne tła
* wizualne wyróżnienie stanów operacyjnych
* dekoracje stadionowe

Funkcjonalnie motyw pozostaje identyczny ze Standard LUMS.

Pomyślna aktualizacja nadal oznacza pomyślną aktualizację.

Nieudane zadanie nadal jest nieudanym zadaniem.

Zmienia się tylko prezentacja.

---

## 31. Golf Club

Motyw **Golf Club** ma celowo odmienną tożsamość wizualną.

Zamiast tradycyjnej estetyki serwerów i infrastruktury interfejs korzysta ze spokojniejszej koncepcji rekreacyjnej.

Kierunek wizualny może akcentować:

* czyste powierzchnie
* powściągliwe dekoracje
* elementy inspirowane golfem
* metafory wizualne nawiązujące do pola golfowego
* spokojną prezentację stanów
* lekkie akcenty tematyczne

Koncepcja pokazuje, że LUMS nie musi wizualnie przypominać tradycyjnej konsoli administracyjnej, aby pozostać funkcjonalny.

Backend i działanie aplikacji pozostają bez zmian.

---

## 32. Nerd Mode

**Nerd Mode** jest przeznaczony dla bardziej technicznej i żartobliwej prezentacji.

Koncepcja może podkreślać techniczny charakter LUMS za pomocą:

* stylów inspirowanych terminalem
* terminologii technicznej
* elementów wizualnych związanych z systemami
* prezentacji w stylu programistycznym
* estetyki diagnostycznej
* celowo technicznych dekoracji

Motyw nadal musi zachować czytelną hierarchię informacji.

Zabawny interfejs nie powinien utrudniać zrozumienia informacji operacyjnych.

---

## 33. Geek Lab

**Geek Lab** przedstawia bardziej eksperymentalne środowisko techniczne.

Koncepcja wizualna może łączyć:

* estetykę laboratorium
* eksperymenty techniczne
* wizualizację infrastruktury
* diagramy systemów
* elementy inspirowane nauką lub inżynierią
* eksperymentalne efekty wizualne

Motyw ma sprawiać wrażenie laboratorium infrastruktury, zachowując pod spodem te same funkcje LUMS.

Eksperymenty wizualne muszą pozostawać odizolowane od aplikacji operacyjnej.

---

## 34. Enterprise Admin

Motyw **Enterprise Admin** przedstawia bardziej zachowawczy interfejs administracyjny.

Może akcentować:

* uporządkowane informacje
* zwarte układy
* pulpity administracyjne
* czytelne wskaźniki stanu
* dużą gęstość informacji operacyjnych
* ograniczenie dekoracji

Motyw jest szczególnie odpowiedni dla użytkowników preferujących konwencjonalny wygląd konsoli administracyjnej.

Nie wprowadza dodatkowych uprawnień administracyjnych.

Nazwa opisuje koncepcję wizualną, a nie poziom autoryzacji.

---

## 35. Porównanie motywów

Motywy można traktować jako różne wizualne interpretacje tej samej aplikacji:

| Motyw | Kierunek wizualny | Główny charakter |
| --- | --- | --- |
| Standard LUMS | Przejrzysty / funkcjonalny | Interfejs referencyjny |
| LUMS Stadium | Stadion / wydarzenia | Ekspresyjny |
| Golf Club | Rekreacyjny / spokojny | Zrelaksowany |
| Nerd Mode | Techniczny / żartobliwy | Dla programistów |
| Geek Lab | Eksperymentalny / techniczny | Laboratoryjny |
| Enterprise Admin | Uporządkowany / administracyjny | Zachowawczy |

Tabela opisuje wyłącznie koncepcje prezentacji.

**Nie** opisuje różnic w zakresie:

* uprawnień
* funkcji
* dostępu do API
* dostępu do klientów
* wykonywania zadań
* zarządzania pakietami
* bezpieczeństwa

---

## 36. Ten sam interfejs, inna prezentacja

Głównym celem projektu jest zachowanie rozpoznawalności tego samego komponentu aplikacji we wszystkich motywach.

Na przykład:

```text
Client List
   │
   ├── Standard presentation
   ├── Stadium presentation
   ├── Golf presentation
   ├── Nerd presentation
   ├── Geek presentation
   └── Enterprise presentation
```

Podstawowe dane klienta pozostają identyczne.

Zmienia się tylko ich prezentacja.

To samo dotyczy:

* inwentarzy oprogramowania
* dostępnych aktualizacji
* zadań aktualizacji
* historii zadań
* informacji o użytkownikach
* stanu systemu
* interfejsów zarządzania pakietami

---

## 37. Stany operacyjne

Motywy mogą wizualnie wyróżniać różne stany operacyjne.

Na przykład:

```text
PENDING
RUNNING
SUCCESS
FAILED
```

Motyw może inaczej przedstawiać te stany, ale ich znaczenie semantyczne musi pozostać spójne.

Motyw nie może zmieniać definicji stanów aplikacji.

Na przykład:

```text
SUCCESS ≠ "looks green"

SUCCESS = actual LUMS job state
```

Prezentacja wizualna jedynie pokazuje stan backendu.

---

## 38. Prezentacja błędów

Motywy mogą też zmieniać wizualny sposób przedstawiania błędów.

Informacje o błędach muszą jednak pozostać zrozumiałe.

Motyw nie powinien:

* ukrywać ważnych informacji o błędzie
* zastępować informacji technicznych dekoracyjnym tekstem
* sprawiać, że ostrzeżenia są nieodróżnialne od zwykłych stanów
* tłumić awarii operacyjnych

Styl wizualny może poprawiać prezentację, ale nie może usuwać informacji diagnostycznych potrzebnych do zrozumienia problemu.

---

## 39. Spójność stanów

Ten sam stan musi mieć spójne znaczenie semantyczne w każdym motywie.

Na przykład:

| Stan | Znaczenie |
| --- | --- |
| Oczekuje | Oczekuje na wykonanie |
| W toku | Jest obecnie przetwarzany |
| Sukces | Zakończono pomyślnie |
| Niepowodzenie | Wykonanie zakończyło się błędem |

Motyw może przedstawiać stany za pomocą różnych kolorów, ikon, typografii lub układów.

Ich podstawowe znaczenie musi pozostać niezmienione.

---

## 40. Dekoracje właściwe dla motywu

Elementy dekoracyjne powinny mieć niższy priorytet niż informacje operacyjne.

Przykłady:

* tła
* wzory
* ilustracje
* efekty otoczenia
* ikony tematyczne
* ozdobniki wizualne

Należy zachować następującą hierarchię:

```text
Operational Information
        │
        ▼
Application Usability
        │
        ▼
Accessibility
        │
        ▼
Visual Decoration
```

Dekoracje nigdy nie mogą być ważniejsze od informacji niezbędnych do obsługi LUMS.

---

## 41. Gęstość wizualna

Poszczególne motywy mogą stosować różną gęstość wizualną.

Na przykład:

* Enterprise Admin może stawiać na gęstość informacji.
* Standard LUMS może zapewniać równowagę i czytelność.
* Golf Club może wykorzystywać więcej pustej przestrzeni.
* Nerd Mode może używać zwartych elementów technicznych.
* Stadium może eksponować duże obszary stanu.
* Geek Lab może dostarczać więcej kontekstu wizualnego.

Są to różnice w prezentacji.

Nie zmieniają ilości ani wiarygodności podstawowych danych.

---

## 42. Dostępność we wszystkich motywach

Każdy motyw musi zachować podstawową użyteczność. Obejmuje to:

* czytelny tekst
* dostateczne rozróżnienie wizualne
* użyteczne kontrolki
* zrozumiałe wskaźniki stanu
* obsługę klawiaturą
* użyteczne i widoczne stany fokusu
* zgodność z preferencją ograniczenia ruchu

Kolor nie może być jedynym sposobem przekazywania ważnego stanu.

Na przykład nieudane zadanie nie powinno być rozpoznawalne wyłącznie po użytym kolorze.

---

## 43. Animacje właściwe dla motywu

Motywy mogą zawierać animacje, jeśli poprawiają koncepcję wizualną.

Przykłady:

* subtelne przejścia
* animowane tła
* efekty sieciowe
* przejścia stanów
* dekoracje otoczenia

Animacje powinny pozostawać drugorzędne wobec aplikacji.

Nie mogą:

* uniemożliwiać interakcji
* zasłaniać kontrolek
* nieustannie odwracać uwagi od danych operacyjnych
* utrudniać dostępności
* wpływać na działanie backendu

---

## 44. Żywa sieć

Niektóre motywy LUMS mogą wykorzystywać dynamiczną warstwę wizualną inspirowaną siecią.

Koncepcja przedstawia LUMS jako żywe środowisko infrastruktury:

```text
Client ─────┐
            │
Client ─────┼──── LUMS
            │
Client ─────┘
```

Taka wizualizacja jest dekoracyjna, chyba że została jawnie połączona z rzeczywistymi danymi aplikacji.

Nie wolno interpretować wizualizacji sieci jako autorytatywnej topologii, o ile aplikacja jawnie nie udostępnia takich informacji.

To istotne rozróżnienie:

> **Wizualizacja nie jest automatycznie telemetrią operacyjną.**

---

## 45. Dane dekoracyjne a rzeczywiste dane

Efekty wizualne właściwe dla motywu muszą być wyraźnie oddzielone od rzeczywistych danych LUMS.

Na przykład:

```text
Decorative node
    ≠
Real client

Animated connection
    ≠
Real network connection

Visual status effect
    ≠
Backend job state
```

Zapobiega to myleniu estetycznej wizualizacji z rzeczywistymi informacjami o systemie.

---

## 46. Tożsamość motywu

Każdy motyw powinien mieć rozpoznawalną tożsamość, ale nie może stać się osobnym produktem.

Cel:

```text
Different visual identity
          +
Same LUMS functionality
          =
Optional LUMS Theme
```

System pozostaje dzięki temu elastyczny i kreatywny, a jednocześnie zachowuje techniczną spójność aplikacji.

---

## 47. Zasada projektowania motywów

Najważniejsza zasada projektowa wszystkich motywów brzmi:

> **Motyw może być ekspresyjny, nietypowy, techniczny, żartobliwy lub zachowawczy, ale zawsze musi pozostać LUMS.**

Niezależnie od wybranej prezentacji wizualnej aplikacja musi być rozpoznawalna jako ten sam system.

# LUMS — Opcjonalny system motywów

## Część 4 — Implementacja frontendu i dostępność

## 48. Warstwa motywów frontendu

Opcjonalny system motywów należy w całości do frontendu LUMS.

Jego odpowiedzialność ogranicza się do prezentacji i obsługi preferencji użytkownika.

Koncepcyjnie:

```text
┌─────────────────────────────────┐
│          LUMS Frontend          │
│                                 │
│  Common Application Logic       │
│              │                  │
│              ▼                  │
│       Theme Presentation        │
│              │                  │
│              ▼                  │
│       Browser Rendering         │
└─────────────────────────────────┘
```

Warstwa motywów nie zastępuje wspólnej logiki frontendu.

Zamiast tego dodaje wokół niej warstwę prezentacji.

---

## 49. Inicjalizacja motywu

Inicjalizacja motywu powinna stanowić część normalnego procesu uruchamiania frontendu.

Koncepcyjna sekwencja:

```text
Frontend starts
      │
      ▼
Theme system initializes
      │
      ▼
Stored preference is evaluated
      │
      ▼
Theme availability is checked
      │
      ├── Valid → selected theme
      │
      └── Invalid → standard theme
      │
      ▼
LUMS interface rendered
```

Inicjalizacja powinna być lekka i nie może zależeć od dostępności backendu.

Użytkownik powinien móc załadować prezentację wizualną nawet wtedy, gdy później nie powiedzie się żądanie API.

---

## 50. Stan motywu

Aktywny motyw jest stanem frontendu.

Należy go więc traktować inaczej niż stan aplikacji.

### Stan motywu

Przykłady:

```text
Active visual theme
Reduced-motion preference
Visual presentation preferences
```

### Stan aplikacji

Przykłady:

```text
Logged-in user
User role
Client state
Package state
Update state
Job state
Audit state
```

Stan motywu nigdy nie może nadpisywać ani podszywać się pod stan aplikacji.

---

## 51. Atrybut motywu na elemencie głównym

Atrybut elementu głównego jest odpowiednią koncepcyjną reprezentacją aktywnego motywu.

Na przykład:

```html
<html data-theme="standard">
```

albo:

```html
<html data-theme="nerd">
```

CSS może wykorzystywać aktywny motyw jako selektor.

Dokładna implementacja może ewoluować, ale cel architektoniczny pozostaje ten sam:

> **Jedna struktura aplikacji, wiele definicji prezentacji.**

---

## 52. Organizacja CSS

Style właściwe dla motywów powinny być odróżnialne od wspólnych stylów LUMS.

Koncepcyjnie:

```text
Common styles
│
├── Layout
├── Forms
├── Tables
├── Navigation
├── Status elements
└── Shared components

Theme styles
│
├── Standard
├── Stadium
├── Golf
├── Nerd
├── Geek
└── Admin
```

Style wspólne definiują układ, formularze, tabele, nawigację, elementy stanu i współdzielone komponenty. Style motywów definiują warianty Standard, Stadium, Golf, Nerd, Geek i Admin.

Style wspólne powinny określać strukturę funkcjonalną.

Style motywów powinny określać tożsamość wizualną.

Ogranicza to duplikację i ułatwia późniejsze utrzymanie motywów.

---

## 53. Zmienne CSS

Systemy motywów mogą wykorzystywać własne właściwości CSS, aby oddzielić wartości semantyczne od ich reprezentacji wizualnej.

Na przykład:

```css
:root {
    --lums-background: ...;
    --lums-surface: ...;
    --lums-text: ...;
    --lums-accent: ...;
}
```

Motyw może następnie podać własne wartości:

```css
[data-theme="example"] {
    --lums-background: ...;
    --lums-surface: ...;
    --lums-text: ...;
    --lums-accent: ...;
}
```

W miarę możliwości komponenty powinny korzystać ze zmiennych semantycznych zamiast wpisywać na stałe wartości właściwe dla motywu.

---

## 54. Współdzielone komponenty

System motywów powinien stylować współdzielone komponenty, a nie je powielać.

Typowe komponenty:

* nawigacja
* przyciski
* formularze
* tabele
* wskaźniki stanu
* karty
* okna dialogowe
* elementy zarządzania pakietami
* elementy zadań aktualizacji
* informacje o klientach
* informacje o systemie

Ten sam komponent powinien działać identycznie niezależnie od aktywnego motywu.

---

## 55. Zasoby motywów

Opcjonalne motywy mogą korzystać z dedykowanych zasobów.

Możliwe kategorie:

```text
Images
Icons
Backgrounds
Decorative graphics
Fonts
Animation assets
Visual effects
```

Zasoby motywów powinny pozostać zasobami frontendu.

Nie mogą zawierać wrażliwych informacji o aplikacji.

W szczególności nie mogą zawierać:

* haseł
* kluczy tajnych
* tokenów klientów
* zawartości bazy danych
* certyfikatów prywatnych
* materiałów uwierzytelniających

---

## 56. Ładowanie zasobów

Zasoby motywu powinny być ładowane tylko wtedy, gdy są potrzebne.

Sama obecność motywu nie powinna niepotrzebnie zwiększać kosztu każdej strony LUMS.

W miarę możliwości:

```text
Selected theme
      │
      ▼
Required assets
      │
      ▼
Browser
```

zamiast:

```text
All themes
      │
      ▼
All assets loaded simultaneously
```

Ma to coraz większe znaczenie w miarę dodawania kolejnych motywów i efektów wizualnych.

---

## 57. Wydajność motywów

Dostosowanie wizualne nie może znacząco pogarszać użyteczności LUMS.

Szczególną uwagę należy zwrócić na:

* duże obrazy tła
* elementy animowane bez przerwy
* efekty canvas
* powtarzające się aktualizacje DOM
* kosztowne filtry wizualne
* niepotrzebne żądania sieciowe

Strony operacyjne, takie jak listy klientów, inwentarze oprogramowania i widoki zadań aktualizacji, powinny pozostać responsywne.

---

## 58. Dekoracyjny JavaScript

Motyw może używać JavaScriptu do obsługi efektów wizualnych, takich jak animowane tła, wizualizacje sieci, dynamiczne dekoracje i interakcje właściwe dla motywu.

Taki JavaScript musi być odizolowany od logiki operacyjnej aplikacji.

Skrypt dekoracyjny nigdy nie może odpowiadać za:

* autoryzację
* tworzenie zadań
* instalowanie ani usuwanie pakietów
* wykonywanie aktualizacji
* uwierzytelnianie klientów
* rejestrowanie audytu

Rozróżnienie musi pozostać jasne:

```text
Theme JavaScript
      ≠
LUMS operational JavaScript
```

---

## 59. Wizualizacja sieci

Jeśli motyw wykorzystuje wizualizację sieci, należy ją traktować jako komponent prezentacji.

Na przykład:

```text
Canvas / Visual Layer
        │
        ▼
Decorative Network
        │
        ▼
Theme Presentation
```

Jeśli wizualizacja nie jest jawnie połączona z autorytatywnymi danymi LUMS, nie powinna sugerować, że przedstawia rzeczywisty stan sieci.

Zapobiega to myleniu dekoracyjnej grafiki z monitorowaniem lub telemetrią.

---

## 60. Ograniczenie ruchu

Motywy korzystające z animacji powinny obsługiwać preferencje ograniczenia ruchu.

Preferowane zachowanie koncepcyjne:

```text
prefers-reduced-motion: reduce
            │
            ▼
Reduce or disable decorative motion
```

Podstawowe funkcje muszą pozostać niezmienione.

Ograniczenie ruchu powinno wpływać wyłącznie na prezentację.

---

## 61. Fokus i nawigacja klawiaturą

Style motywów muszą zachować obsługę klawiaturą.

Ważne elementy interaktywne powinny nadal mieć widoczne stany fokusu.

Motywy nie powinny usuwać obramowania fokusu bez zapewnienia równie czytelnego rozwiązania zastępczego.

Na przykład:

```text
Keyboard focus
      │
      ▼
Clearly visible control state
```

Dotyczy to:

* nawigacji
* przycisków
* odnośników
* pól formularzy
* selektorów
* okien dialogowych
* elementów zarządzania pakietami

---

## 62. Niezależność od koloru

Ważne informacje nie mogą zależeć wyłącznie od koloru.

Na przykład:

```text
FAILED
```

Stan `FAILED` powinien pozostać zrozumiały dzięki tekstowi, ikonie, strukturze lub innemu dostępnym sposobowi prezentacji, nawet gdy kolory motywu są niedostępne.

Jest to szczególnie istotne, ponieważ motywy mogą używać bardzo różnych palet barw.

---

## 63. Kontrast

Każdy motyw powinien zapewniać dostateczny kontrast między:

* tekstem i tłem
* kontrolkami i tłem
* wskaźnikami stanu i sąsiadującymi elementami
* elementami z fokusem i ich otoczeniem

Interesująca wizualnie paleta nie zastępuje czytelnych informacji.

Gdy kolory motywu kolidują z wymaganiami dostępności, pierwszeństwo ma czytelność.

---

## 64. Interfejs wyboru motywu

Selektor motywu jest częścią wspólnego interfejsu LUMS.

Powinien pozostać zrozumiały niezależnie od aktualnie aktywnego motywu.

Koncepcyjnie:

```text
Theme selector
      │
      ├── Standard LUMS
      ├── LUMS Stadium
      ├── Golf Club
      ├── Nerd Mode
      ├── Geek Lab
      └── Enterprise Admin
```

Wybór innego motywu powinien zmieniać prezentację bez zmiany bieżącej sesji LUMS ani stanu operacyjnego.

---

## 65. Niezależność sesji

Zmiana motywu nie może wylogować użytkownika.

Nie może:

* unieważnić sesji
* zmienić roli
* obrócić tokenów klientów
* zmodyfikować stanu uwierzytelnienia po stronie serwera

Preferencja motywu jest niezależna od uwierzytelniania.

```text
Theme change
     │
     └── Session remains unchanged
```

---

## 66. Niezależność od RBAC

Motywy muszą być niezależne od RBAC.

Na przykład:

```text
Administrator
     │
     └── sees functionality permitted to administrators

Operator
     │
     └── sees functionality permitted to operators

Viewer
     │
     └── sees functionality permitted to viewers
```

Wybrany motyw nie zmienia tych uprawnień.

Viewer korzystający z Enterprise Admin nie staje się administratorem.

Administrator korzystający z Nerd Mode nie traci uprawnień administracyjnych.

W każdym przypadku autorytatywnym podmiotem pozostaje backend.

---

## 67. Izolowanie błędów

Awaria opcjonalnej funkcji wizualnej nie powinna przerywać podstawowego działania LUMS.

Na przykład, jeśli awarii ulegnie dekoracyjna animacja:

```text
Animation failure
      │
      ▼
Theme remains usable
      │
      ▼
LUMS remains operational
```

W miarę możliwości funkcje wizualne powinny ulegać awarii niezależnie od funkcjonalności aplikacji.

Jest to szczególnie istotne w przypadku opcjonalnych efektów, takich jak animowane tła i wizualizacje sieci.

---

## 68. Zgodność z przeglądarkami

System motywów powinien korzystać z funkcji przeglądarek obsługiwanych przez przeglądarki docelowe środowiska wdrożeniowego LUMS.

Jeśli funkcja wizualna jest niedostępna, interfejs powinien łagodnie przejść do rozwiązania zastępczego, zamiast stać się bezużyteczny.

Podstawowym rozwiązaniem zastępczym powinna pozostać prezentacja standardowa.

---

## 69. Zasada implementacji

Implementację można podsumować następująco:

```text
Common HTML
     +
Common LUMS JavaScript
     +
Theme selection
     +
Theme-specific CSS/assets
     =
Optional visual layer
```

Poniższe elementy muszą pozostać poza warstwą motywów:

```text
Authentication
Authorization
Database
Jobs
Package management
Client authentication
Audit logging
Security decisions
```

Ten podział pozwala motywom być ekspresyjnymi, nie wiążąc ich z podstawowym działaniem LUMS.

# LUMS — Opcjonalny system motywów

## Część 5 — Bezpieczeństwo, testy i rozwój

## 70. Granica bezpieczeństwa

System motywów jest częścią frontendu, a zatem działa w niezaufanym środowisku klienta.

Przeglądarka kontroluje warstwę prezentacji.

Przeglądarka **nie** kontroluje autoryzacji LUMS.

Granica bezpieczeństwa pozostaje następująca:

```text
Browser
   │
   │ untrusted presentation
   ▼
LUMS API
   │
   │ authoritative validation
   ▼
LUMS Backend
```

Wszystkie decyzje istotne dla bezpieczeństwa muszą zatem pozostać po stronie serwera.

---

## 71. Wybór motywu nie jest autoryzacją

Wybranego motywu nigdy nie wolno interpretować jako sygnału autoryzacji.

Na przykład:

```text
data-theme="admin"
```

nie oznacza, że bieżący użytkownik jest administratorem.

Słowo `admin` w identyfikatorze motywu ma wyłącznie charakter opisowy.

Rzeczywista rola użytkownika musi zawsze wynikać z uwierzytelnionej sesji aplikacji i logiki autoryzacji po stronie serwera.

---

## 72. Widoczność w frontendzie nie jest zabezpieczeniem

Motyw lub skrypt frontendu może ukryć element interfejsu.

Służy to prezentacji.

Nie wystarcza do kontroli dostępu.

```text
Hidden button
      ≠
Unauthorized operation prevented
```

Odpowiedni endpoint API musi niezależnie sprawdzać uprawnienia użytkownika.

Dotyczy to wszystkich uprzywilejowanych funkcji LUMS.

---

## 73. Zasoby motywów są publiczne

Zasoby frontendu należy traktować jako publicznie dostępne dla wszystkich, którzy mogą korzystać z interfejsu webowego LUMS.

Dlatego pliki motywów nigdy nie mogą zawierać sekretów.

Nie umieszczaj w zasobach motywów:

```text
Passwords
API secrets
Client tokens
Private keys
Database files
Session secrets
Authentication credentials
```

Informacje, które muszą pozostać poufne, nie należą do zasobów motywu.

---

## 74. Żadnych sekretów backendu w motywach

JavaScript motywu nie może zawierać poświadczeń serwera ani uprzywilejowanych danych API.

W razie potrzeby motyw powinien komunikować się z istniejącą warstwą aplikacji frontendowej.

Nie może wprowadzać alternatywnego mechanizmu uwierzytelniania.

> **Motywy korzystają z danych prezentacji; nie tworzą poświadczeń bezpieczeństwa.**

---

## 75. Cross-Site Request Forgery

Funkcje motywu nie mogą omijać istniejącej ochrony CSRF.

Jeśli motyw udostępnia element interfejsu uruchamiający operację wymagającą chronionego żądania, żądanie musi spełniać te same wymagania bezpieczeństwa co wspólny interfejs LUMS.

Wizualny charakter kodu nie zwalnia motywu z tych wymagań.

---

## 76. Korzystanie z API

Motyw powinien unikać samodzielnego implementowania logiki operacyjnej API.

Gdy potrzebuje danych aplikacji, powinien korzystać z ustalonych mechanizmów aplikacji frontendowej LUMS.

Zapobiega to tworzeniu niezależnych implementacji:

* uwierzytelniania
* żądań API
* obsługi błędów
* założeń dotyczących autoryzacji
* obsługi zadań

Wspólna logika aplikacji pozostaje autorytatywną warstwą integracji frontendu.

---

## 77. Izolacja motywów

Usunięcie motywu nie powinno usuwać podstawowych funkcji LUMS.

Koncepcyjnie:

```text
Remove optional theme
        │
        ▼
Standard LUMS remains
        │
        ▼
Application remains operational
```

Dzięki temu motywy są naprawdę opcjonalne.

---

## 78. Testy bezpieczeństwa

Testy bezpieczeństwa powinny potwierdzać, że zmiana motywu nie wpływa na model bezpieczeństwa LUMS.

Warto sprawdzić, czy:

* Viewer nadal jest użytkownikiem Viewer
* Operator nadal jest użytkownikiem Operator
* Administrator nadal jest użytkownikiem Administrator
* chronione endpointy API pozostają chronione
* ochrona CSRF pozostaje aktywna
* uwierzytelnianie klientów się nie zmienia
* uprawnienia do zadań aktualizacji się nie zmieniają
* uprawnienia do zarządzania pakietami się nie zmieniają
* rejestrowanie audytu się nie zmienia

Sam motyw nigdy nie może być dowodem bezpieczeństwa operacji.

---

## 79. Testy funkcjonalne motywów

Każdy motyw należy sprawdzić we wspólnej aplikacji.

Co najmniej:

```text
Login
Client list
Client details
Installed software
Available updates
Update jobs
Job history
Package management
User management
System maintenance
Logout
```

Dokładny zestaw dostępnych funkcji zależy od roli uwierzytelnionego użytkownika.

Test ma potwierdzić, że renderowanie motywu nie psuje normalnego działania aplikacji.

---

## 80. Testy motywów z RBAC

Testy motywów powinny obejmować wszystkie odpowiednie role.

| Rola | Testy motywu |
| --- | --- |
| Administrator | Wymagane |
| Operator | Wymagane |
| Viewer | Wymagane |

Dla każdej roli sprawdź, czy zmiana motywu nie zmienia dozwolonych funkcji.

Na przykład:

```text
Viewer + Nerd Mode
        =
Viewer permissions

Viewer + Enterprise Admin
        =
Viewer permissions
```

Motyw wizualny nie może zmieniać wyniku.

---

## 81. Testy przełączania motywów

Przełączanie motywów należy testować wielokrotnie, na przykład:

```text
Standard
   ↓
Stadium
   ↓
Golf
   ↓
Nerd
   ↓
Geek
   ↓
Admin
   ↓
Standard
```

Aplikacja powinna pozostać użyteczna przez cały przebieg testu.

Zwróć szczególną uwagę na:

* zmiany układu
* tabele
* nawigację
* okna dialogowe
* formularze
* wskaźniki stanu
* długi tekst
* zachowanie responsywne

---

## 82. Testy trwałości preferencji

Jeśli preferencja motywu jest zapisywana lokalnie, wykonaj następujące testy:

1. Wybierz motyw.
2. Odśwież stronę.
3. Sprawdź, czy motyw nadal jest wybrany.
4. Zamknij przeglądarkę.
5. Ponownie otwórz LUMS.
6. Sprawdź, czy preferencja nadal jest prawidłowo obsługiwana.
7. Usuń lub unieważnij zapisany motyw.
8. Sprawdź, czy nastąpił powrót do motywu standardowego.

Zapisana wartość nigdy nie może być traktowana jako stan bezpieczeństwa aplikacji.

---

## 83. Testowanie nieprawidłowego motywu

Nieprawidłowy identyfikator motywu nie powinien uszkadzać interfejsu.

Na przykład:

```text id="4j5cqn"
unknown-theme
```

Powinien skutkować bezpiecznym rozwiązaniem zastępczym, a nie bezużyteczną stroną.

Oczekiwane zachowanie:

```text
Invalid theme
     │
     ▼
Standard theme
     │
     ▼
LUMS remains usable
```

---

## 84. Testowanie awarii zasobów

Należy również sprawdzić awarie opcjonalnych zasobów.

Przykłady:

* brak obrazu
* niedostępna animacja
* nieprawidłowa ścieżka zasobu
* nieobsługiwana funkcja wizualna
* błąd JavaScriptu w opcjonalnej dekoracji

W miarę możliwości wspólna aplikacja powinna pozostać użyteczna.

---

## 85. Testowanie ograniczenia ruchu

W przypadku motywów z animacjami przetestuj zarówno środowisko z normalnym ruchem, jak i z jego ograniczeniem.

```text id="l1h4nb"
Normal motion
     │
     └── Theme effects available

Reduced motion
     │
     └── Effects reduced or disabled
```

Ważne kontrolki aplikacji muszą działać w pełni w obu przypadkach.

---

## 86. Testowanie układu responsywnego

Motywy należy sprawdzać przy różnych rozmiarach okna:

* widok na komputerze
* okno o rozmiarze tabletu
* wąskie okno lub widok mobilny

Tożsamość wizualna nie może ograniczać użyteczności kontrolek ani czytelności danych aplikacji.

Zwróć szczególną uwagę na:

* nawigację
* tabele
* przyciski działań
* kontrolki zarządzania pakietami
* informacje o stanie zadań
* okna dialogowe
* selektory motywów

---

## 87. Testy wydajności

Należy ocenić wpływ efektów wizualnych na wydajność przeglądarki.

Warto obserwować:

* czas ładowania strony
* responsywność renderowania
* użycie procesora
* użycie pamięci
* płynność animacji
* powtarzające się aktualizacje DOM
* żądania sieciowe

Motywy powinny poprawiać prezentację, a nie stawać się wąskim gardłem wydajności.

---

## 88. Przepływ pracy przy tworzeniu

W miarę możliwości nowy motyw należy tworzyć niezależnie od zmian backendu.

Zalecany przebieg:

```text
Design
   ↓
Frontend implementation
   ↓
Theme selector integration
   ↓
Accessibility review
   ↓
Functional testing
   ↓
RBAC testing
   ↓
Fallback testing
   ↓
Performance review
   ↓
Documentation
```

Zmiany backendu należy wprowadzać tylko wtedy, gdy istnieje rzeczywiste wymaganie aplikacji.

Motyw wizualny zwykle nie powinien wymagać modyfikacji backendu.

---

## 89. Zasady tworzenia

Podczas tworzenia motywu:

1. Używaj ponownie istniejących komponentów LUMS.
2. Unikaj powielania stron.
3. Izoluj style właściwe dla motywu.
4. Oddziel dekoracyjny JavaScript od logiki operacyjnej.
5. Nie dodawaj logiki uwierzytelniania.
6. Nie dodawaj logiki autoryzacji.
7. Nie ujawniaj sekretów.
8. Zachowuj dostępność.
9. Zachowuj obsługę ograniczenia ruchu.
10. Testuj wszystkie odpowiednie role.
11. Testuj standardowe rozwiązanie zastępcze.
12. Dokumentuj nowe zasoby i zachowanie.

---

## 90. Weryfikacja zmian

Przed uznaniem zmiany motywu za ukończoną sprawdź zarówno prezentację, jak i funkcjonalność.

Przydatna sekwencja weryfikacji:

```text
Theme changed
      │
      ▼
Visual inspection
      │
      ▼
Page functionality
      │
      ▼
Role behavior
      │
      ▼
API behavior
      │
      ▼
Browser console
      │
      ▼
Regression tests
```

Motyw nie jest ukończony tylko dlatego, że dobrze wygląda.

Musi również pozostawiać działanie LUMS bez zmian.

---

## 91. Zasada regresji

Tworzenie motywów powinno opierać się na ogólnej zasadzie stosowanej w innych zmianach LUMS:

> **Zmień → Przetestuj → Zweryfikuj → Udokumentuj**

Zmiana wizualna również może spowodować regresje funkcjonalne, na przykład:

* ukryte przyciski
* nieczytelny tekst
* uszkodzony układ
* niedostępne kontrolki
* konflikty JavaScriptu
* brakujące zasoby
* nieprawidłowe selektory
* błędy układu mobilnego

Testowanie jest częścią tworzenia motywu, a nie opcjonalnym etapem końcowym.

---

## 92. Rozwiązywanie problemów: motyw się nie ładuje

Jeśli wybrany motyw się nie pojawia:

1. Odśwież stronę.
2. Sprawdź, czy ładuje się motyw standardowy.
3. Sprawdź konsolę przeglądarki.
4. Sprawdź, czy identyfikator wybranego motywu jest prawidłowy.
5. Sprawdź dostępność wymaganych zasobów motywu.
6. Poszukaj błędów JavaScriptu.
7. W razie potrzeby wyczyść lokalną preferencję motywu.
8. Odśwież stronę i sprawdź standardowe rozwiązanie zastępcze.

Nie zmieniaj konfiguracji bezpieczeństwa backendu, aby naprawić problem wizualny frontendu.

---

## 93. Rozwiązywanie problemów: motyw psuje układ

Jeśli motyw powoduje problemy z układem:

1. Przełącz się na Standard LUMS.
2. Sprawdź, czy wspólny interfejs działa.
3. Zidentyfikuj dotknięty komponent.
4. Sprawdź CSS właściwy dla motywu.
5. Sprawdź zachowanie responsywne.
6. Sprawdź błędy w konsoli przeglądarki.
7. Popraw style właściwe dla motywu.
8. Ponownie przetestuj pozostałe motywy.

Motyw standardowy stanowi ważny punkt odniesienia przy diagnozowaniu.

---

## 94. Rozwiązywanie problemów: motyw powoduje błędy JavaScriptu

Jeśli JavaScript właściwy dla motywu powoduje błędy:

1. Przełącz się na motyw standardowy.
2. Potwierdź prawidłowe działanie funkcji LUMS.
3. Znajdź skrypt motywu, który powoduje awarię.
4. Ustal, czy błąd dotyczy dekoracji, czy aplikacji.
5. Usuń błąd właściwy dla motywu.
6. Sprawdź, czy wspólny JavaScript LUMS pozostał niezmieniony.
7. Ponownie przetestuj przełączanie motywów.

Nie modyfikuj JavaScriptu operacyjnego tylko po to, aby skompensować błąd dekoracyjnego motywu.

---

## 95. Rozwiązywanie problemów: nieprawidłowa preferencja motywu

Jeśli lokalnie nadal jest zapisany stary lub nieprawidłowy motyw:

```text
Invalid stored preference
        │
        ▼
Fallback to Standard
        │
        ▼
Select a valid theme
```

Preferowanym rozwiązaniem jest bezpieczny powrót do motywu standardowego, a nie ręczna ingerencja w backend.

---

## 96. Dokumentacja motywów

Dokumentacja każdego nowego motywu powinna zawierać:

* identyfikator wewnętrzny
* nazwę wyświetlaną
* koncepcję wizualną
* wymagane zasoby
* opcjonalne efekty wizualne
* kwestie dostępności
* zachowanie przy ograniczonym ruchu
* znane ograniczenia

Dokumentacja implementacji powinna opisywać rzeczywisty bieżący kod, a nie przypuszczenia dotyczące działania motywu.

---

## 97. Obecny zestaw motywów

Obecnie udokumentowane koncepcje motywów:

```text
standard       → Standard LUMS
LUMSStadium    → LUMS Stadium
golf           → Golf Club
nerd           → Nerd Mode
geek           → Geek Lab
admin          → Enterprise Admin
```

Zestaw motywów można rozszerzać.

Można dodawać kolejne motywy bez zmieniania architektury LUMS, o ile zachowany zostanie podział między prezentacją a działaniem aplikacji.

---

## 98. Zasada tworzenia

Opcjonalny system motywów powinien pozostać kontrolowanym rozszerzeniem frontendu.

Ma zwiększać ekspresyjność i dostosowanie LUMS bez komplikowania jego obsługi operacyjnej.

Preferowana architektura:

```text id="l2e8o9"
Common LUMS
     │
     ├── Common functionality
     ├── Common security
     ├── Common backend
     └── Common application state
              │
              ▼
       Optional Theme Layer
              │
       ┌──────┼──────┐
       ▼      ▼      ▼
    Theme A Theme B Theme C
```

Wspólna aplikacja pozostaje fundamentem.

Motywy pozostają opcjonalnymi rozszerzeniami.

# LUMS — Opcjonalny system motywów

## Część 6 — Utrzymanie, rozszerzenia i stan końcowy

## 99. Utrzymanie motywów

W miarę możliwości utrzymanie motywów powinno być oddzielone od utrzymania podstawowego LUMS.

Aktualizacja wizualna zwykle powinna obejmować wyłącznie zasoby frontendu.

Typowe zmiany:

* korekty CSS
* zasoby wizualne
* JavaScript właściwy dla motywu
* usprawnienia dostępności
* poprawki układu responsywnego
* korekty animacji
* zmiany nazwy lub prezentacji motywu

Aktualizacja motywu nie powinna wymagać zmian w:

* konfiguracji klientów
* tokenach klientów
* schemacie bazy danych
* zadaniach aktualizacji
* logice zarządzania pakietami
* uwierzytelnianiu
* RBAC
* zabezpieczeniach po stronie serwera

Jeśli zmiana motywu niespodziewanie wymaga takich modyfikacji, przed kontynuowaniem należy przeanalizować zależność.

---

## 100. Aktualizacje motywów

Aktualizacje motywów powinny przebiegać zgodnie ze zwykłym procesem LUMS:

```text
Modify
   ↓
Test
   ↓
Verify
   ↓
Document
```

W przypadku większych zmian:

```text
Design
   ↓
Implementation
   ↓
Functional testing
   ↓
Accessibility testing
   ↓
RBAC regression testing
   ↓
Performance review
   ↓
Documentation
```

Motywu nie należy uznawać za ukończony wyłącznie dlatego, że efekt wizualny wygląda poprawnie.

---

## 101. Dodawanie nowego motywu

Nowy motyw można wprowadzić bez zmiany backendu LUMS.

Zalecany proces:

### Krok 1 — Zdefiniuj koncepcję

Opisz:

* tożsamość wizualną
* docelowy styl
* typografię
* kolory
* elementy dekoracyjne
* opcjonalne animacje

### Krok 2 — Zdefiniuj identyfikator

Wybierz stabilny identyfikator wewnętrzny.

### Krok 3 — Przygotuj prezentację

Dodaj wymagane style i zasoby.

### Krok 4 — Zintegruj wybór

Udostępnij motyw we wspólnym selektorze motywów.

### Krok 5 — Przetestuj

Sprawdź:

* zwykłe strony
* kontrolki interaktywne
* układy responsywne
* dostępność
* ograniczenie ruchu
* wszystkie odpowiednie role RBAC
* zachowanie zastępcze

### Krok 6 — Udokumentuj

Zapisz informacje o motywie i istotne szczegóły jego implementacji.

---

## 102. Usuwanie motywu

Usunięcie motywu należy traktować jako zmianę zgodności dla użytkowników, którzy mogą nadal mieć ten motyw lokalnie wybrany.

Frontend powinien bezpiecznie obsługiwać nieaktualny identyfikator.

```text
Old theme identifier
       │
       ▼
Theme no longer available
       │
       ▼
Standard LUMS
```

Usunięcie motywu nigdy nie powinno wymagać migracji bazy danych tylko po to, aby usunąć preferencję zapisaną w przeglądarce.

---

## 103. Zmiana nazwy motywu

Nazwę wyświetlaną można zwykle zmienić niezależnie od identyfikatora wewnętrznego.

Na przykład:

```text id="8q4n1k"
Internal identifier
        │
        └── remains stable

Display name
        │
        └── may change
```

Jeśli zmienia się sam identyfikator, może być potrzebna migracja albo mapa zgodności dla istniejących preferencji lokalnych.

W miarę możliwości należy zachowywać stabilność identyfikatorów.

---

## 104. Zgodność motywów

Motywy powinny pozostawać zgodne ze zmianami wspólnego interfejsu LUMS.

Po dodaniu współdzielonego komponentu należy sprawdzić w istniejących motywach:

* brakujące style
* uszkodzone odstępy
* nieczytelny tekst
* nieprawidłowe kolory
* brak zachowania responsywnego
* nieprawidłowe stany fokusu
* niedostępne kontrolki

Nowa funkcja backendu nie wymaga automatycznie nowej funkcji motywu.

Źródłem prawdy pozostaje wspólna aplikacja.

---

## 105. Nowe funkcje LUMS

Po dodaniu nowej funkcji do LUMS jej zgodność z motywami należy zwykle ocenić po uruchomieniu wspólnej funkcji.

Zalecana kolejność:

```text
New LUMS feature
       │
       ▼
Common implementation
       │
       ▼
Functional tests
       │
       ▼
Theme compatibility
       │
       ▼
Theme-specific refinement
```

Zapobiega to uzależnieniu rozwoju podstawowych funkcji od dostosowań wizualnych.

---

## 106. Stabilność API motywów

System motywów powinien unikać tworzenia osobnej warstwy API, chyba że istnieje rzeczywista potrzeba.

Motywy powinny korzystać ze wspólnego stanu aplikacji frontendowej i mechanizmów API już używanych przez LUMS.

Ogranicza to:

* powielanie logiki żądań
* powielanie obsługi błędów
* niespójne założenia dotyczące autoryzacji
* dodatkowe prace utrzymaniowe
* niepotrzebną powierzchnię ataku

Dlatego system motywów jest celowo lekki.

---

## 107. Przegląd bezpieczeństwa motywu

Podczas dodawania lub istotnej zmiany motywu sprawdź:

```text
[ ] No credentials in assets
[ ] No client tokens in assets
[ ] No private keys
[ ] No authentication bypass
[ ] No authorization logic
[ ] No CSRF bypass
[ ] No direct security decisions
[ ] No unintended API endpoints
[ ] No sensitive information in frontend assets
[ ] Decorative scripts remain isolated
```

Przegląd należy przeprowadzić nawet wtedy, gdy zmiana wydaje się wyłącznie wizualna.

Kod frontendu nadal jest wykonywalnym kodem.

---

## 108. Przegląd dostępności motywu

Dla każdego motywu sprawdź:

```text
[ ] Text remains readable
[ ] Contrast remains sufficient
[ ] Focus states are visible
[ ] Keyboard navigation works
[ ] Controls remain usable
[ ] Statuses are not color-only
[ ] Reduced motion is respected
[ ] Responsive layout remains usable
[ ] Decorative effects do not obscure information
```

Dostępność należy traktować jako element jakości motywu, a nie opcjonalne ulepszenie.

---

## 109. Lista kontrolna regresji motywu

Przed zaakceptowaniem zmiany motywu sprawdź:

```text
[ ] Standard theme works
[ ] Changed theme works
[ ] Other themes still work
[ ] Theme switching works
[ ] Stored preference works
[ ] Invalid preference falls back safely
[ ] Login works
[ ] Logout works
[ ] Client views work
[ ] Software views work
[ ] Update views work
[ ] Package-management views work
[ ] User-management views work where authorized
[ ] Job information remains readable
[ ] Error messages remain understandable
[ ] RBAC remains unchanged
[ ] Backend behavior remains unchanged
```

Dokładny zestaw widocznych funkcji zależy od roli użytkownika testowego.

---

## 110. Niezależność operacyjna

Opcjonalny system motywów jest celowo niezależny od operacyjnego cyklu życia LUMS.

Zmiana motywu nie może wymagać:

```text
Agent restart
Watcher restart
Database restart
Client re-registration
Token rotation
Job cancellation
Package-manager changes
Network changes
```

Dzięki temu warstwa prezentacji może rozwijać się niezależnie od warstwy infrastruktury.

---

## 111. Niezależność wdrażania

Zasoby motywów są częścią frontendu aplikacji LUMS.

Ogólne procedury wdrażania opisują główne przewodniki instalacji i administracji.

Ten dokument celowo nie powiela:

* procedur wdrażania Dockera
* poleceń utwardzania kontenera
* konfiguracji Nginx
* procedur kopii zapasowej bazy danych
* procedur odzyskiwania serwera
* procedur instalacji klientów

Te zagadnienia należą do właściwej dokumentacji operacyjnej.

Rozdzielenie tematów zapobiega dezaktualizacji dokumentacji motywów przy zmianie architektury wdrożenia.

---

## 112. Rozdzielenie źródła i środowiska uruchomieniowego

System motywów należy rozumieć jako część kodu źródłowego aplikacji.

Należy rozróżniać:

```text
Source
   │
   ├── Theme definitions
   ├── CSS
   ├── JavaScript
   └── Assets

Runtime
   │
   ├── Built LUMS image
   └── Running LUMS application
```

Zmiana motywu w kodzie źródłowym nie oznacza automatycznie, że otrzymało ją już działające wdrożenie.

Za dostarczenie zaktualizowanych zasobów frontendu odpowiada zwykły proces budowania i wdrażania LUMS.

---

## 113. Wersjonowanie

Motywy nie muszą wprowadzać osobnej wersji backendu LUMS.

Motyw może ewoluować w ramach wersji frontendu lub aplikacji.

Jeśli zmiana motywu powoduje problemy ze zgodnością, należy je jawnie udokumentować.

Na przykład:

```text id="5y1p8f"
Theme change
     │
     ├── visual-only
     │
     └── compatibility-affecting
```

Druga kategoria wymaga dodatkowych testów regresji.

---

## 114. Gotowość wydania

Przed wydaniem LUMS zawierającym zmiany motywów sprawdź:

```text
Theme rendering
Theme selection
Theme fallback
Accessibility
Reduced motion
Responsive layout
RBAC behavior
API behavior
Security boundaries
Regression tests
Documentation
```

Zmiany motywów nie mogą ukrywać regresji podstawowych funkcji aplikacji.

---

## 115. Obecny zestaw motywów

Obecnie udokumentowane koncepcje motywów:

| Identyfikator | Nazwa wyświetlana | Koncepcja |
| --- | --- | --- |
| `standard` | Standard LUMS | Interfejs referencyjny |
| `LUMSStadium` | LUMS Stadium | Stadion / wydarzenia |
| `golf` | Golf Club | Spokojny / rekreacyjny |
| `nerd` | Nerd Mode | Techniczny / żartobliwy |
| `geek` | Geek Lab | Eksperymentalny / techniczny |
| `admin` | Enterprise Admin | Uporządkowany / administracyjny |

Motywy korzystają z tej samej aplikacji LUMS i tego samego backendu.

Są wariantami wizualnymi, a nie odrębnymi produktami ani poziomami uprawnień.

---

## 116. Bieżący stan

Opcjonalny system motywów jest rozszerzeniem architektury frontendu LUMS.

Jego zamierzone właściwości:

```text
[✓] Optional
[✓] Client-side presentation
[✓] Common backend
[✓] Common security model
[✓] Common RBAC model
[✓] Standard fallback
[✓] Theme-specific visual identity
[✓] Reduced-motion consideration
[✓] Accessibility consideration
[✓] No theme-based authorization
```

Szczegóły właściwe dla implementacji należy zawsze synchronizować z bieżącym kodem frontendu.

---

## 117. Przyszłe rozszerzenia

System motywów można rozszerzać na kilka sposobów bez zmiany podstawowej architektury.

Możliwe przyszłe dodatki:

* kolejne motywy
* ulepszone podglądy motywów
* bardziej szczegółowe preferencje wizualne
* dodatkowe ustawienia dostępności
* lepsze zachowanie responsywne
* układy pulpitów właściwe dla motywów
* dodatkowe opcjonalne wizualizacje

Takie rozszerzenia powinny nadal zachowywać podział między prezentacją a działaniem aplikacji.

---

## 118. Architektura końcowa

Całą koncepcję można podsumować następująco:

```text
                    LUMS
                     │
          ┌──────────┴──────────┐
          │                     │
     Application             Theme Layer
          │                     │
          │             ┌───────┼────────┐
          │             │       │        │
          │          Standard Stadium  Golf
          │
          │             Nerd   Geek   Admin
          │
          └──────────────┬──────────────┘
                         │
                         ▼
                  Common Backend
                         │
             ┌───────────┼───────────┐
             │           │           │
          Security      Jobs       Clients
             │           │           │
             └───────────┼───────────┘
                         ▼
                      SQLite
```

Warstwa wizualna pozostaje opcjonalna.

Warstwa aplikacji pozostaje autorytatywna.

Warstwa bezpieczeństwa pozostaje niezależna.

---

## 119. Zasada końcowa

Opcjonalny system motywów ma uczynić LUMS bardziej osobistym, ekspresyjnym i elastycznym bez naruszania architektury technicznej.

Podstawowa zasada pozostaje niezmienna:

> **Jeden LUMS · wiele interfejsów · ten sam backend**

Motyw może zmienić atmosferę LUMS.

Nigdy nie może zmienić tego, co LUMS faktycznie może robić.
