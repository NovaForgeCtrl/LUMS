# LUMS — Przewodnik administracji

> **Zarządzanie aktualizacjami Linuksa bez zbędnego szumu.**

Ten przewodnik opisuje codzienną administrację i eksploatację LUMS po zainstalowaniu serwera i klientów.

Koncentruje się na zadaniach administracyjnych wykonywanych przez interfejs webowy LUMS oraz na kontrolowanych zadaniach operacyjnych na serwerze LUMS i zarządzanych klientach.

Procedury instalacji są opisane osobno w `install.md`.

Procedury rozwiązywania problemów są opisane osobno w `troubleshooting.md`.

Architektura bezpieczeństwa i informacje audytowe są opisane osobno w `security.md`.

---

## Pierwsze kroki: codzienna administracja

Ten przewodnik jest przeznaczony dla osoby odpowiedzialnej za istniejącą instalację LUMS.
Szczegółowe sekcje techniczne są prowadzone w języku angielskim. Zacznij od tych
pojęć:

* **Konto użytkownika:** określa, co dana osoba może robić w interfejsie webowym LUMS.
  Nie udostępniaj kont; każda osoba powinna mieć własne konto.
* **Klient:** zarządzany komputer z Linuksem. Jego token klienta jest sekretem i nie
  jest tym samym co hasło konta webowego.
* **Zadanie aktualizacji:** żądana operacja, którą agent pobiera i wykonuje
  za pomocą APT lub pacman na komputerze docelowym. Przed uruchomieniem sprawdź
  cel i pakiety.
* **Kopia zapasowa:** osobna, zweryfikowana kopia bazy danych. Kopia w tym samym
  wolumenie Docker nie chroni przed utratą tego wolumenu.
* **Aktualizacja:** zastępuje wersję kontenera, a nie bazę danych. Normalna
  aktualizacja nie może usuwać ani odtwarzać `lums-data`.

### Bezpieczna lista kontrolna przed wprowadzeniem zmiany

1. Sprawdź, czy uruchomione są zadania aktualizacji i czy potrzebne jest okno
   konserwacyjne.
2. Potwierdź, że istnieje ostatnia, użyteczna kopia zapasowa bazy danych.
3. Zapisz uruchomiony obraz, ustawienia kontenera i ścieżki danych.
4. Zbuduj i przetestuj nowy obraz przed zatrzymaniem aktywnego kontenera.
5. Zastąp kontener tymi samymi montowaniami danych, sekretów i kopii zapasowych oraz
   tymi samymi opcjami bezpieczeństwa.
6. Sprawdź status kontenera, logi, logowanie HTTPS i dane po uruchomieniu.
7. Zachowaj stary kontener jako opcję wycofania, dopóki nowa wersja nie zostanie
   zweryfikowana.

**Nie uruchamiaj** `docker volume rm lums-data`, `docker system prune --volumes`
ani innych poleceń usuwających dane w ramach normalnej aktualizacji. Mogą one trwale
usunąć dane. Jeśli nie masz pewności, który kontener lub ścieżka są aktywne, zatrzymaj się i
najpierw sprawdź bieżącą konfigurację; nie kopiuj przykładowego polecenia bez
sprawdzenia go.

---

## 1. Przegląd administracji

LUMS zapewnia scentralizowaną administrację inwentarzem oprogramowania Linuksa, dostępnymi aktualizacjami, operacjami na pakietach, zadaniami aktualizacji, zarządzanymi klientami, użytkownikami i historią operacyjną.

Interfejs administracyjny udostępnia trzy szablony ról:

* **Administrator**
* **Operator**
* **Viewer**

Przy tworzeniu konta wybrana rola wypełnia zalecany zestaw
uprawnień. Administratorzy mogą dostosować te uprawnienia dla każdego użytkownika; o dostępie decydują zapisane
uprawnienia, a nie etykieta roli.

LUMS oddziela również operacje administracyjne po stronie serwera od wykonywania pakietów po stronie klienta.

Normalny przepływ operacyjny to:

```text
Administrator / Operator
        │
        ▼
   LUMS Web UI
        │
        ▼
     LUMS API
        │
        ▼
      SQLite
        │
        ▼
   Managed Client
        │
        ▼
 APT / pacman / system
        │
        ▼
      Result
        │
        ▼
     LUMS API
        │
        ▼
      SQLite
        │
        ▼
    Web Interface
```

Serwer LUMS nie wykonuje bezpośrednio poleceń zarządzania pakietami na zarządzanych klientach.

Operacje na pakietach są wykonywane przez Agenta LUMS zainstalowanego na zarządzanym systemie.

---

## 2. Obowiązki administracyjne

Administrację LUMS można podzielić na kilka obszarów.

### Administracja użytkownikami

Administratorzy zarządzają:

* użytkownikami LUMS
* rolami użytkowników
* statusem kont
* dostępem administracyjnym

Zarządzanie użytkownikami wymaga uprawnienia `users.manage`.

Szablon Administratora domyślnie zawiera to uprawnienie.

Operatorzy i Viewerzy domyślnie go nie otrzymują.

---

### Administracja klientami

Administratorzy zarządzają:

* zarejestrowanymi klientami
* statusem klientów
* uwierzytelnianiem klientów
* tokenami klientów
* rotacją tokenów
* włączaniem i wyłączaniem klientów

Administracja klientami wymaga uprawnienia `clients.manage`, ponieważ
uwierzytelnianie klientów określa, które systemy mogą raportować do LUMS.

---

### Administracja aktualizacjami

Szablony Administratora i Operatora przyznają uprawnienia do:

* przeglądania dostępnych aktualizacji
* tworzenia zadań aktualizacji
* wykonywania operacji na pakietach
* przeglądania historii aktualizacji
* zarządzania pojedynczymi pakietami
* wykonywania aktualizacji systemu

Szablon Viewera jest tylko do odczytu i nie może wykonywać operacji aktualizacji.

---

### Administracja pakietami

LUMS obsługuje operacje zarządzania pakietami przez natywny menedżer pakietów klienta.

Obecnie obsługiwane backendy zarządzania pakietami obejmują:

* **APT/dpkg** dla systemów opartych na Debianie
* **pacman** dla Arch Linux

LUMS nie zastępuje menedżera pakietów systemu operacyjnego.

Zamiast tego LUMS zapewnia scentralizowany interfejs do żądania i śledzenia operacji na pakietach.

---

### Administracja operacyjna

Administratorzy i Operatorzy mogą potrzebować monitorować:

* uruchomione zadania aktualizacji
* nieudane zadania
* zakończone zadania
* raportowanie klientów
* wymagania ponownego uruchomienia
* błędy menedżera pakietów
* aktywność audytową

Szczegółowe procedury rozwiązywania problemów dla tych stanów są opisane w `troubleshooting.md`.

---

## 3. Role administracyjne

LUMS obecnie udostępnia trzy role.

| Rola          | Przeznaczenie                                  |
| ------------- | ---------------------------------------------- |
| Administrator | Pełna kontrola administracyjna                 |
| Operator      | Codzienne zarządzanie operacyjne               |
| Viewer        | Widoczność klientów i oprogramowania tylko do odczytu |

Każda rola jest szablonem uprawnień. Indywidualnie zapisane
uprawnienia konta są egzekwowane po stronie serwera.

Ukrycie elementu interfejsu nie jest więc samo w sobie uznawane za mechanizm bezpieczeństwa.

Nieautoryzowane operacje API również muszą być odrzucane przez serwer.

---

## 4. Administrator

Szablon Administratora domyślnie zapewnia pełny zestaw uprawnień aplikacji LUMS.

Administratorzy mogą:

* przeglądać zarządzanych klientów
* przeglądać zainstalowane oprogramowanie
* przeglądać dostępne aktualizacje
* tworzyć i wykonywać zadania aktualizacji
* przeglądać historię aktualizacji
* wykonywać operacje zarządzania pakietami
* wykonywać konserwację systemu
* tworzyć klientów
* wyłączać klientów
* rotować tokeny klientów
* tworzyć użytkowników LUMS i zarządzać nimi
* przypisywać szablony ról i indywidualne uprawnienia

Pełne uprawnienia szablonu Administratora powinny być przyznawane tylko użytkownikom, którzy
ich wymagają.

Konta administracyjne nie powinny być używane do rutynowego monitorowania tylko do odczytu, gdy wystarczy konto Operatora lub Viewera.

---

## 5. Operator

Szablon Operatora jest przeznaczony do codziennej aktualizacji i administracji systemem.

Operatorzy mogą:

* przeglądać zarządzanych klientów
* przeglądać zainstalowane oprogramowanie
* przeglądać dostępne aktualizacje
* tworzyć i wykonywać zadania aktualizacji
* przeglądać historię aktualizacji
* wykonywać operacje zarządzania pakietami
* wykonywać konserwację systemu

Szablon Operatora nie przyznaje:

* tworzenia użytkowników LUMS ani zarządzania nimi
* przypisywania ról użytkowników
* tworzenia lub wyłączania klientów
* rotacji tokenów klientów

Ten domyślny podział pozwala na rutynowe operacje aktualizacji bez przyznawania
uprawnień do zarządzania kontami i klientami. Indywidualne nadania mogą być zmieniane przez
użytkownika z `users.manage`.

---

## 6. Viewer

Szablon Viewera zapewnia widoczność tylko do odczytu.

Viewerzy mogą:

* przeglądać zarządzanych klientów
* przeglądać zainstalowane oprogramowanie

Szablon Viewera nie przyznaje następujących funkcji administracyjnych:

* zarządzania dostępnymi aktualizacjami
* tworzenia zadań aktualizacji
* wykonywania zadań aktualizacji
* historii aktualizacji
* zarządzania pakietami
* konserwacji systemu
* zarządzania użytkownikami
* zarządzania klientami
* rotacji tokenów

Odpowiednie zmieniające stan operacje API są również chronione po stronie serwera.

Dostęp Viewera jest więc przeznaczony dla użytkowników, którzy potrzebują widoczności bez kontroli operacyjnej.

---

## 7. Wytyczne wyboru roli

Używaj najmniejszej roli, która zapewnia wymaganą funkcjonalność.

### Administrator

Używaj, gdy użytkownik musi zarządzać:

* użytkownikami
* rolami
* klientami
* uwierzytelnianiem klientów
* tokenami
* aktualizacjami
* pakietami
* operacjami systemowymi

### Operator

Używaj, gdy użytkownik musi wykonywać rutynową pracę operacyjną, taką jak:

* sprawdzanie aktualizacji
* instalowanie pakietów
* usuwanie pakietów
* aktualizowanie pakietów
* wykonywanie zadań aktualizacji
* przeglądanie historii zadań

### Viewer

Używaj, gdy użytkownik potrzebuje tylko widoczności:

* klientów
* zainstalowanego oprogramowania

---

## 8. Administracyjna zasada bezpieczeństwa

Administracja LUMS kieruje się zasadą najmniejszych uprawnień.

Dostęp administracyjny powinien być ograniczony do funkcjonalności wymaganej do zadania użytkownika.

W szczególności:

* nie używaj kont Administratora do rutynowego przeglądania
* nie udostępniaj kont między administratorami
* nie udostępniaj tokenów klientów
* nie umieszczaj poświadczeń w dokumentacji
* nie ujawniaj tokenów klientów na zrzutach ekranu ani w logach
* nie omijaj interfejsu webowego LUMS przez bezpośrednią modyfikację bazy danych, chyba że udokumentowana procedura odzyskiwania wyraźnie tego wymaga

Gdy operacja administracyjna zakończy się niepowodzeniem, zbadaj przyczynę przed zmianą trwałego stanu.

Stosuj zasadę:

> **Najpierw obserwuj. Potem zmieniaj. Na końcu weryfikuj.**

---

## 9. Przepływ pracy administracyjnej

Normalny przepływ pracy administracyjnej powinien przebiegać w tej kolejności:

```text
1. Uwierzytelnienie
      │
      ▼
2. Weryfikacja roli
      │
      ▼
3. Wybór klienta / operacji
      │
      ▼
4. Przegląd bieżącego stanu
      │
      ▼
5. Wykonanie wymaganej operacji
      │
      ▼
6. Monitorowanie zadania
      │
      ▼
7. Weryfikacja wyniku
      │
      ▼
8. Przegląd historii / informacji audytowych
```

Działania administracyjne powinny być zawsze weryfikowane po wykonaniu.

Pomyślne żądanie API samo w sobie nie dowodzi, że żądana operacja na pakiecie lub systemie została zakończona pomyślnie.

Istotnym wynikiem operacyjnym jest końcowy stan zgłoszony przez zarządzanego klienta.

---

## 10. Podział dokumentacji

Zestaw dokumentacji LUMS jest celowo podzielony na osobne przewodniki operacyjne.

| Dokument             | Przeznaczenie                                 |
| -------------------- | --------------------------------------------- |
| `install.md`         | Instalacja i wstępne wdrożenie                |
| `administration.md`  | Codzienna administracja                       |
| `security.md`        | Architektura bezpieczeństwa i wyniki audytu   |
| `troubleshooting.md` | Diagnoza i odzyskiwanie                       |

Ten przewodnik powinien więc unikać duplikowania szczegółowych procedur instalacji i rozwiązywania problemów.

Zamiast tego opisuje, czym administratorzy mogą zarządzać, co oznacza każda operacja i jak wykonywane są normalne przepływy pracy administracyjnej.

## 11. Zarządzanie użytkownikami

Zarządzanie użytkownikami jest dostępne dla użytkowników z uprawnieniem `users.manage`.

Administratorzy mogą tworzyć konta aplikacji LUMS i zarządzać nimi przez dedykowany interfejs zarządzania użytkownikami.

Konta użytkowników są oddzielne od uwierzytelniania zarządzanych klientów.

Użytkownik LUMS uwierzytelnia się w aplikacji webowej za pomocą konta aplikacji.

Zarządzany klient uwierzytelnia się w API LUMS za pomocą tokena klienta.

Tych mechanizmów uwierzytelniania nie wolno mylić.

```text
LUMS User
    │
    │ username + password
    ▼
Web Interface
    │
    ▼
LUMS Application

Managed Client
    │
    │ client token
    ▼
LUMS API
```

---

## 12. Tworzenie użytkowników

Użytkownicy z `users.manage` mogą tworzyć nowych użytkowników LUMS.

Podczas tworzenia użytkownika Administrator określa:

* nazwę użytkownika
* hasło
* etykietę roli, z szablonem roli dostępnym do późniejszego przypisania uprawnień

Dostępne szablony ról to:

* `administrator`
* `operator`
* `viewer`

Serwer waliduje podane wartości przed utworzeniem konta.

Nowe konta zaczynają bez uprawnień. Po utworzeniu administratorzy mogą
przypisać indywidualne pola wyboru lub zastosować jeden z szablonów ról. Zastosowanie
szablonu wstępnie zaznacza jego domyślne uprawnienia, które następnie można dostosować.
Dostępne uprawnienia to:

| Uprawnienie       | Przyznawany dostęp                                      |
| ----------------- | ------------------------------------------------------- |
| `clients.view`    | Przeglądanie listy klientów i informacji o systemie     |
| `software.view`   | Przeglądanie zainstalowanego oprogramowania             |
| `updates.view`    | Przeglądanie aktualizacji, zadań i historii aktualizacji |
| `packages.search` | Wyszukiwanie w repozytoriach pakietów                   |
| `jobs.manage`     | Tworzenie operacji na pakietach i zadań aktualizacji    |
| `clients.manage`  | Rejestrowanie/usuwanie klientów i rotacja tokenów klientów |
| `users.manage`    | Tworzenie użytkowników i zarządzanie rolami, uprawnieniami oraz notatkami wewnętrznymi |
| `backups.manage`  | Tworzenie i przeglądanie kopii zapasowych bazy danych   |

Uprawnienia związane z klientami wymagają `clients.view`; `jobs.manage` wymaga również
`updates.view`. LUMS uniemożliwia usunięcie ostatniego aktywnego konta z
`users.manage`, więc administratorzy nie mogą przypadkowo zablokować sobie dostępu.

Hasła nie są przechowywane jako tekst jawny.

LUMS używa hashowania haseł opartego na Argon2 dla poświadczeń aplikacji.

Po utworzeniu sprawdź, czy:

* nazwa użytkownika pojawia się na liście użytkowników
* szablon roli i indywidualne uprawnienia są poprawne
* konto jest włączone
* użytkownik może się pomyślnie uwierzytelnić

Nie przekazuj haseł przez dokumentację, zgłoszenia, zrzuty ekranu ani inne niezabezpieczone kanały.

---

## Interfejs kopii zapasowych bazy danych

Użytkownicy z uprawnieniem `backups.manage` mogą tworzyć kopie zapasowe SQLite z
**Datenbank-Backups**. Konta Administratora otrzymują to uprawnienie przez
migrację `005-backup-permission`; nowe konta otrzymują je przez zastosowanie
szablonu Administratora lub mogą je otrzymać jawnie.

Interfejs obsługuje natywne pliki `.db` i skompresowane `.db.gz`. Używa
API kopii zapasowej online SQLite, waliduje ukończoną bazę danych i przechowuje pliki
z uprawnieniami tylko dla właściciela. Interfejs użytkownika wyświetla dziesięć najnowszych plików. Kopie zapasowe
nie są szyfrowane, automatycznie usuwane, planowane, pobierane ani przywracane przez
LUMS; administratorzy z `backups.manage` mogą usuwać pojedyncze kopie zapasowe z
listy po potwierdzeniu. Odpowiednio chroń miejsce docelowe.

Bazowy katalog docelowy jest ustalany przez ustawienie serwera `LUMS_BACKUP_DIR`.
Interfejs pozwala wybrać względny podkatalog poniżej tej bazy i tworzy go w razie potrzeby; ścieżki bezwzględne, przechodzenie do katalogu nadrzędnego i
podkatalogi będące dowiązaniami symbolicznymi są odrzucane. Ścieżki hosta muszą być zamontowane w Docker
przez administratora serwera. Dla wdrożenia Docker utwórz osobny katalog hosta
zapisywalny przez UID/GID kontenera `10001`:

```bash
sudo install -d -o 10001 -g 10001 -m 0700 /var/backups/lums
```

Dodaj te opcje do konfiguracji kontenera LUMS:

```bash
-v /var/backups/lums:/var/backups/lums \
-e LUMS_BACKUP_DIR=/var/backups/lums \
```

Używaj osobnego dysku lub zdalnego magazynu dla odporności na awarię hosta.
Na przykład zamontuj NAS najpierw na hoście Debian, a następnie użyj tej zamontowanej ścieżki
jako lewej strony montowania bind w Docker. Interfejs kopii zapasowych wyświetla
katalog bazowy po stronie kontenera; wybrana ścieżka względna znajduje się poniżej niego.
Miejsce docelowe kopii zapasowych musi być dostępne i zapisywalne wewnątrz kontenera;
w przeciwnym razie interfejs zgłasza, że magazyn kopii zapasowych jest niedostępny.

Kroki przywracania opisano w [`server/static/backup-restore.md`](server/static/backup-restore.md).

---

## 13. Role użytkowników

Wybierz szablon roli zgodnie z minimalnym wymaganym uprawnieniem, a następnie
przejrzyj indywidualne uprawnienia dla każdego konta.

| Szablon roli  | Zarządzanie użytkownikami | Zarządzanie klientami | Aktualizacje | Zarządzanie pakietami | Dostęp tylko do odczytu |
| ------------- | ------------------------: | --------------------: | -----------: | --------------------: | ----------------------: |
| Administrator |                       Tak |                   Tak |          Tak |                   Tak |                     Tak |
| Operator      |                        Nie |                   Nie |          Tak |                   Tak |                     Tak |
| Viewer        |                        Nie |                   Nie |          Nie |                   Nie |                     Tak |

To są wartości domyślne, a nie sztywne granice. Administratorzy mogą dostosować zestaw uprawnień każdego
użytkownika. Egzekwowanie ról odbywa się po stronie serwera przez
wynikowe uprawnienia poszczególnych użytkowników.

Interfejs webowy odzwierciedla przypisaną rolę, ale serwer pozostaje autorytatywną granicą bezpieczeństwa.

---

## 14. Wyłączanie kont użytkowników

Gdy konto nie powinno już mieć dostępu do LUMS, wyłącz konto, zamiast udostępniać lub zmieniać przeznaczenie poświadczeń.

Przykłady obejmują:

* administrator odchodzi z projektu
* operator nie potrzebuje już dostępu
* tymczasowe odebranie dostępu administracyjnego
* reakcja bezpieczeństwa na przejęte konto

Po wyłączeniu konta sprawdź, czy uwierzytelnianie jest odrzucane.

Podczas dochodzeń dotyczących bezpieczeństwa konta należy również uwzględnić istniejące uwierzytelnione sesje.

Nie modyfikuj ręcznie tabeli `users`, chyba że udokumentowana procedura odzyskiwania wyraźnie wymaga interwencji na poziomie bazy danych.

---

## 15. Administracja hasłami

Hasła są poświadczeniami aplikacji i muszą być traktowane jako informacje wrażliwe.

Administratorzy powinni zapewnić, że:

* hasła nie są udostępniane
* hasła nie są przechowywane w Git
* hasła nie są umieszczane w dokumentacji
* hasła nie są umieszczane na zrzutach ekranu
* hasła nie są niepotrzebnie zapisywane w historii powłoki
* użytkownicy otrzymują poświadczenia przez odpowiedni bezpieczny kanał

LUMS przechowuje skróty haseł, a nie hasła w postaci jawnej.

Jeśli istnieje podejrzenie, że hasło zostało ujawnione, zastąp je przez odpowiednią procedurę zarządzania kontem, zamiast próbować odzyskać oryginalne hasło.

---

## 16. Sesje

LUMS używa uwierzytelnionych sesji aplikacji do dostępu webowego.

Obsługa sesji jest częścią granicy bezpieczeństwa aplikacji.

Administratorzy powinni traktować nieoczekiwaną uwierzytelnioną sesję jako zdarzenie bezpieczeństwa, jeśli powiązane konto nie powinno już mieć dostępu.

Istotne sytuacje obejmują:

* wyłączone konto nadal wyglądające na aktywne
* nieoczekiwany dostęp administracyjny
* podejrzenie przejęcia poświadczeń
* nieoczekiwana sesja przeglądarki
* dochodzenie bezpieczeństwa

Szczegółowe informacje o rozwiązywaniu problemów z sesjami i uwierzytelnianiem znajdują się w `troubleshooting.md`.

---

## 17. Ograniczanie szybkości logowania

LUMS stosuje ograniczanie szybkości dla powtarzających się nieudanych prób logowania.

Obecna progresja to:

| Nieudane próby |     Blokada |
| -------------: | ----------: |
|              5 |   30 sekund |
|              6 |   60 sekund |
|              7 |  120 sekund |
|             8+ | 300 sekund  |

Stan ograniczania szybkości jest utrwalany w SQLite.

Udane logowanie czyści odpowiedni stan nieudanych prób.

Powtarzające się błędy uwierzytelniania należy zbadać, a nie omijać ogranicznik szybkości.

Możliwe przyczyny obejmują:

* nieprawidłowe poświadczenia
* nieaktualne zapisane poświadczenia
* zautomatyzowany klient używający nieprawidłowych poświadczeń
* powtarzające się ręczne próby logowania
* możliwy atak na poświadczenia

---

## 18. Zarządzanie klientami

Zarządzani klienci to systemy Linux z uruchomionym Agentem LUMS.

Klient dostarcza LUMS informacje takie jak:

* tożsamość klienta
* zainstalowane oprogramowanie
* dostępne aktualizacje
* wyniki zarządzania pakietami
* wyniki zadań aktualizacji
* stan ponownego uruchomienia
* status operacyjny

Serwer LUMS przechowuje stan klienta i udostępnia go przez interfejs webowy.

Klient wykonuje rzeczywiste operacje zarządzania pakietami lokalnie.

---

## 19. Uwierzytelnianie klientów

Każdy zarządzany klient uwierzytelnia się w LUMS za pomocą tokena klienta.

Token działa jako poświadczenie zarządzanego klienta.

Tokeny klientów traktuj z taką samą ostrożnością jak hasła.

Nigdy nie:

* zatwierdzaj tokenów w Git
* umieszczaj tokenów w publicznej dokumentacji
* umieszczaj tokenów na zrzutach ekranu
* wklejaj tokenów do systemów zgłoszeń
* ujawniaj tokenów w danych diagnostycznych
* udostępniaj tokena jednego klienta innemu klientowi

Token powinien być zainstalowany tylko na kliencie, dla którego został wydany.

---

## 20. Rejestracja klienta

Nowy klient musi najpierw zostać zarejestrowany w LUMS.

Proces rejestracji ustanawia tożsamość klienta po stronie serwera i poświadczenie uwierzytelniania.

Po rejestracji:

1. zainstaluj Agenta LUMS
2. skonfiguruj token klienta
3. skonfiguruj endpoint serwera LUMS
4. ustanów zaufanie TLS
5. wykonaj początkowe uruchomienie agenta
6. sprawdź, czy klient raportuje pomyślnie
7. potwierdź, że klient pojawia się w interfejsie LUMS

Klienta nie należy uznawać za operacyjnego tylko dlatego, że usługa Agenta uruchomiła się pomyślnie.

Serwer musi otrzymać i zaakceptować prawidłowy raport klienta.

---

## 21. Status klienta

Widok klienta powinien służyć do rozróżniania różnych stanów operacyjnych.

Przykłady obejmują:

* klient zarejestrowany, ale nie raportuje
* klient raportujący normalnie
* klient raportujący nieaktualne informacje
* klient wyłączony
* błąd uwierzytelniania klienta
* błąd menedżera pakietów po stronie klienta

Gdy klient przestaje raportować, najpierw ustal, czy problem dotyczy:

1. łączności sieciowej
2. zaufania TLS
3. uwierzytelniania klienta
4. wykonania Agenta
5. dostępności serwera
6. przetwarzania po stronie serwera

Unikaj zmiany poświadczeń klienta przed ustaleniem, która warstwa faktycznie zawodzi.

---

## 22. Rotacja tokenów klientów

Tokeny klientów można rotować, gdy jest to wymagane.

Typowe powody obejmują:

* podejrzenie ujawnienia tokena
* politykę rotacji poświadczeń
* konserwację administracyjną
* zastąpienie konfiguracji klienta
* reakcję na incydent bezpieczeństwa

Rotacja tokenów zmienia poświadczenie akceptowane dla klienta.

Po rotacji:

1. uzyskaj nowy token klienta
2. zaktualizuj konfigurację klienta
3. uruchom Agenta
4. sprawdź pomyślne uwierzytelnienie
5. sprawdź wynikowy raport klienta
6. potwierdź wznowienie normalnego raportowania

Nie usuwaj starej konfiguracji klienta, dopóki nowa ścieżka uwierzytelniania nie zostanie zweryfikowana.

---

## 23. Wyłączanie klienta

Klienta można wyłączyć, gdy nie powinien już uczestniczyć w operacjach LUMS.

Przykłady obejmują:

* wycofanie systemu z eksploatacji
* tymczasowa konserwacja
* zastąpienie klienta
* podejrzenie ujawnienia poświadczeń

Przed wyłączeniem klienta sprawdź, czy są z nim powiązane aktywne zadania aktualizacji.

Po wyłączeniu:

* sprawdź, czy klient nie jest już traktowany jako operacyjny
* przejrzyj odpowiednią historię zadań aktualizacji
* zachowaj informacje audytowe wymagane do dochodzenia

Nie usuwaj trwałych danych klienta tylko dlatego, że klient jest tymczasowo offline.

---

## 24. Lista kontrolna administracji klientami

Podczas dodawania lub zmiany klienta sprawdź pełny łańcuch:

```text
[ ] Klient istnieje w LUMS
[ ] Klient jest włączony
[ ] Token klienta jest prawidłowy
[ ] Zaufanie TLS jest prawidłowe
[ ] Agent LUMS jest zainstalowany
[ ] Konfiguracja agenta jest prawidłowa
[ ] Początkowy raport kończy się sukcesem
[ ] Klient pojawia się w interfejsie webowym
[ ] Zainstalowane oprogramowanie jest raportowane
[ ] Dostępne aktualizacje są raportowane
[ ] Zadania aktualizacji mogą być śledzone
[ ] Wyniki są zwracane poprawnie
```

Klient jest operacyjny tylko wtedy, gdy działa pełny łańcuch raportowania i uwierzytelniania.

---

## 25. Zasada administracyjna

Administracja użytkownikami i administracja klientami powinny pozostać oddzielne.

Konto aplikacji LUMS określa **co dana osoba może robić**.

Token klienta określa **który zarządzany system może komunikować się z LUMS**.

```text
Application User
      │
      └── Role / Permissions

Managed Client
      │
      └── Client Token / Identity
```

Nie używaj jednego mechanizmu jako substytutu drugiego.

## 26. Inwentarz oprogramowania

LUMS przechowuje informacje o oprogramowaniu raportowane przez zarządzanych klientów.

Inwentarz oprogramowania pozwala administratorom i operatorom ustalić, które pakiety są zainstalowane na kliencie.

Inwentarz jest zbierany przez Agenta LUMS i raportowany do serwera.

Serwer następnie udostępnia raportowane informacje przez interfejs klienta.

Inwentarz należy traktować jako migawkę raportowanego stanu klienta.

Nie zastępuje on natywnego menedżera pakietów.

---

## 27. Zainstalowane oprogramowanie

Sekcja **Zainstalowane oprogramowanie** wyświetla pakiety raportowane przez wybranego klienta.

Administratorzy i Operatorzy mogą używać lokalnego filtra pakietów do zawężenia wyświetlanego inwentarza.

Filtr zainstalowanego oprogramowania jest funkcją lokalnego interfejsu.

Jest oddzielony od wyszukiwania w zarządzaniu pakietami.

To rozróżnienie jest istotne:

```text
Installed Software
    │
    └── Filter already reported package inventory

Package Management
    │
    └── Search the client's package repositories
```

Zainstalowany pakiet może więc nie pojawić się w wyszukiwaniu zarządzania pakietami, jeśli nie jest już dostępny w skonfigurowanym repozytorium.

---

## 28. Dostępne aktualizacje

LUMS zbiera również informacje o pakietach, dla których dostępne są aktualizacje.

Informacje o dostępnych aktualizacjach są generowane na zarządzanym kliencie przy użyciu jego natywnego systemu zarządzania pakietami.

Raportowane informacje można wykorzystać do identyfikacji pakietów wymagających uwagi.

Przed utworzeniem zadania aktualizacji przejrzyj:

* tożsamość klienta
* nazwę pakietu
* obecnie zainstalowaną wersję
* dostępną wersję
* status pakietu
* czy klient jest obecnie osiągalny

Nie zakładaj, że każdą dostępną aktualizację należy natychmiast zainstalować.

Przed wykonaniem należy uwzględnić wymagania operacyjne, okna konserwacyjne, zależności aplikacji i stan klienta.

---

## 29. Zarządzanie pakietami

LUMS zapewnia scentralizowane operacje zarządzania pakietami dla obsługiwanych klientów Linux.

Obecne działania zarządzania pakietami obejmują:

* `INSTALL_PACKAGE`
* `REMOVE_PACKAGE`
* `UPDATE_PACKAGE`
* `UPDATE_SYSTEM`

Operacja jest żądana przez LUMS, ale wykonywana lokalnie przez Agenta LUMS.

Agent przekazuje rzeczywistą operację na pakiecie natywnemu menedżerowi pakietów.

```text
LUMS Web UI
      │
      ▼
LUMS API
      │
      ▼
Update Job
      │
      ▼
LUMS Agent
      │
      ├── APT / dpkg
      │
      └── pacman
```

LUMS pozostaje więc niezależny od bazy danych pakietów i implementacji zarządzania pakietami systemu operacyjnego.

---

## 30. Wyszukiwanie pakietów

Interfejs **Zarządzanie pakietami** zapewnia wyszukiwanie pakietów oddzielone od filtra zainstalowanego oprogramowania.

Wyszukiwanie żąda informacji o pakietach od zarządzanego klienta.

W systemach opartych na Debianie Agent używa narzędzi zarządzania pakietami APT.

W Arch Linux Agent używa `pacman`.

Wyniki wyszukiwania mogą zawierać:

* nazwę pakietu
* wersję pakietu
* opis pakietu
* informacje o repozytorium, jeśli są dostępne

Wyszukiwanie pakietów niczego nie instaluje.

Wyszukiwanie jest więc operacją tylko do odczytu.

---

## 31. Instalowanie pakietu

Administratorzy i Operatorzy mogą tworzyć zadania instalacji pakietów.

Normalny przepływ pracy to:

1. wybierz zarządzanego klienta
2. otwórz **Zarządzanie pakietami**
3. wyszukaj wymagany pakiet
4. przejrzyj wynik
5. wybierz działanie instalacji
6. utwórz zadanie
7. monitoruj wykonanie
8. zweryfikuj wynik
9. odśwież lub ponownie sprawdź zainstalowane oprogramowanie

Pakiet jest instalowany przez Agenta przy użyciu natywnego menedżera pakietów.

Pomyślne utworzenie zadania nie oznacza, że instalacja została już zakończona.

Należy sprawdzić końcowy wynik zadania.

---

## 32. Usuwanie pakietu

Usuwanie pakietu podlega temu samemu kontrolowanemu przepływowi zadań.

Przed usunięciem pakietu sprawdź:

* właściwego klienta
* właściwy pakiet
* zamierzoną operację
* czy inne oprogramowanie nie zależy od tego pakietu

Po wykonaniu sprawdź wynikowy status zadania i raportowany stan oprogramowania klienta.

LUMS nie omija obsługi zależności menedżera pakietów.

Natywny menedżer pakietów pozostaje odpowiedzialny za rozwiązanie operacji.

---

## 33. Aktualizowanie pakietu

Konkretny pakiet można zaktualizować, gdy dostępna jest aktualizacja.

Przepływ pracy to:

```text
Available Update
      │
      ▼
Review Package
      │
      ▼
Create UPDATE_PACKAGE Job
      │
      ▼
Agent Execution
      │
      ▼
Result Validation
```

LUMS waliduje informacje o pakiecie przed utworzeniem odpowiedniego zadania aktualizacji.

Jeśli pakiet nie jest już wymieniony jako aktualizowalny, żądania zadania nie należy traktować jako prawidłowej operacji aktualizacji.

Zapobiega to ślepemu wykonywaniu nieaktualnych informacji o aktualizacjach.

---

## 34. Aktualizowanie systemu

`UPDATE_SYSTEM` wykonuje szerszą aktualizację systemu przy użyciu natywnego mechanizmu zarządzania pakietami klienta.

Ta operacja wpływa na więcej niż jeden pakiet i dlatego należy ją traktować jako operację konserwacyjną.

Przed rozpoczęciem aktualizacji systemu sprawdź:

* dostępność klienta
* okno konserwacyjne
* aktualnie uruchomione zadania
* stan menedżera pakietów
* dostępne miejsce na dysku, jeśli to istotne
* czy może być wymagane ponowne uruchomienie

Po aktualizacji sprawdź:

* wynik zadania
* raport klienta
* zainstalowane oprogramowanie
* dostępne aktualizacje
* stan ponownego uruchomienia

---

## 35. Zadania aktualizacji

Wszystkie zmieniające stan operacje na pakietach i aktualizacjach są reprezentowane jako zadania aktualizacji LUMS.

Zapewnia to wspólny model wykonania i śledzenia.

Typowy cykl życia zadania:

```text
PENDING
   │
   ▼
RUNNING
   │
   ├──────────────► FAILED
   │
   ▼
SUCCESS
```

Zadanie może również wymagać dodatkowej obsługi, gdy klient stanie się niedostępny lub wykonanie zostanie przerwane.

Historii zadań należy używać jako autorytatywnego zapisu operacyjnego, zamiast polegać wyłącznie na bieżącym widoku klienta.

---

## 36. Tworzenie zadań

Przed utworzeniem zadania aktualizacji dokładnie sprawdź zamierzoną operację.

Sprawdź:

* klienta
* działanie
* pakiet
* wersję docelową, jeśli dotyczy
* bieżący stan pakietu
* wymagania konserwacyjne

Obsługiwane działania obejmują:

| Działanie         | Przeznaczenie                 |
| ----------------- | ----------------------------- |
| `INSTALL_PACKAGE` | Instalacja pakietu            |
| `REMOVE_PACKAGE`  | Usunięcie pakietu             |
| `UPDATE_PACKAGE`  | Aktualizacja konkretnego pakietu |
| `UPDATE_SYSTEM`   | Aktualizacja całego systemu   |

Tworzenie zadań aktualizacji jest ograniczone do ról **Administrator** i **Operator**.

Viewerzy nie mogą tworzyć zadań aktualizacji.

---

## 37. Wykonywanie zadań

Po utworzeniu zadanie jest przetwarzane przez Agenta LUMS.

Agent otrzymuje zadanie i wykonuje żądaną operację lokalnie.

Serwer śledzi wynikowy stan.

Agent nie traktuje pomyślnego żądania HTTP jako dowodu, że operacja na pakiecie zakończyła się sukcesem.

Zamiast tego rzeczywisty wynik menedżera pakietów jest zwracany do LUMS.

To rozróżnienie jest istotne:

```text
API request accepted
        ≠
Package operation successful
```

Dlatego zawsze należy sprawdzić końcowy wynik wykonania.

---

## 38. Wyniki zadań

Zakończone zadanie powinno zawierać jednoznaczny wynik.

Istotne rezultaty obejmują:

* pomyślne wykonanie
* nieudane wykonanie
* błąd menedżera pakietów
* przerwane wykonanie
* stan związany z odzyskiwaniem
* stan związany z ponownym uruchomieniem, jeśli dotyczy

Administratorzy i Operatorzy powinni sprawdzić wynik, gdy zadanie zakończy się niepowodzeniem, zamiast natychmiast powtarzać tę samą operację.

Powtarzanie wykonania bez zrozumienia pierwotnej awarii może utrudnić diagnozę.

---

## 39. Historia zadań

Historia aktualizacji zapewnia operacyjny zapis poprzedniej aktywności aktualizacyjnej.

Używaj jej do odpowiedzi na pytania takie jak:

* Czy ten pakiet został już zaktualizowany?
* Który klient wykonał operację?
* Kiedy utworzono zadanie?
* Kiedy rozpoczęło się wykonanie?
* Kiedy zakończyło się wykonanie?
* Czy operacja zakończyła się sukcesem?
* Czy menedżer pakietów zgłosił błąd?

Informacje historyczne o zadaniach są szczególnie ważne podczas badania powtarzających się awarii lub przerwanych operacji konserwacyjnych.

---

## 40. Nieudane zadania

Gdy zadanie zakończy się niepowodzeniem:

1. zapisz klienta i ID zadania
2. sprawdź wynik zadania
3. ustal, czy awaria wystąpiła na serwerze, czy na kliencie
4. sprawdź odpowiednie logi Agenta
5. sprawdź stan natywnego menedżera pakietów
6. usuń podstawową przyczynę
7. ponów dopiero po zrozumieniu przyczyny

Typowe przyczyny obejmują:

* niedostępne repozytoria
* blokady menedżera pakietów
* problemy sieciowe
* nieprawidłowe żądania pakietów
* konflikty zależności
* niewystarczające miejsce na dysku
* przerwane operacje na pakietach
* problemy z uwierzytelnianiem lub komunikacją klienta

Szczegółowe procedury diagnostyczne są opisane w `troubleshooting.md`.

---

## 41. Blokady menedżera pakietów

APT i pacman mogą uniemożliwiać równoczesne operacje na pakietach.

Jeśli operacja zarządzania pakietami nie powiedzie się, ponieważ menedżer pakietów jest już używany:

* zidentyfikuj aktywny proces zarządzania pakietami
* ustal, która operacja jest uruchomiona
* w odpowiednim przypadku poczekaj na zakończenie legalnej operacji
* następnie ponów operację LUMS

**Nie** usuwaj bezrefleksyjnie plików blokad menedżera pakietów, gdy menedżer pakietów jest uruchomiony.

Usunięcie pliku blokady nie rozwiązuje podstawowej równoczesnej operacji i może uszkodzić stan zarządzania pakietami.

---

## 42. Wykonywanie z uwzględnieniem bezczynności

LUMS może używać informacji o bezczynności klienta do określenia, czy zadanie aktualizacji powinno zostać wykonane.

Mechanizm ten ma na celu uniknięcie przerwania aktywnego interaktywnego użytkowania zarządzanego systemu.

Wykrywanie bezczynności jest wykonywane przez Agenta na kliencie.

Jeśli informacje o bezczynności są niedostępne, Agent musi zgłosić ten stan, a nie wymyślać stanu bezczynności.

Administratorzy powinni rozróżniać:

* klient jest bezczynny
* klient jest aktywny
* wykrywanie bezczynności jest niedostępne
* klient jest nieosiągalny

Te stany mają różne znaczenie operacyjne.

---

## 43. Monitorowanie wykonywania aktualizacji

Podczas konserwacji monitoruj:

* stan zadania
* łączność z klientem
* aktywność Agenta
* wynik menedżera pakietów
* wymaganie ponownego uruchomienia

Nie zakładaj, że zadanie pozostające w stanie `RUNNING` bez końca oznacza, że menedżer pakietów nadal pracuje.

Jeśli wykonanie wydaje się zawieszone, zbadaj stan klienta i Agenta przed utworzeniem kolejnego zadania.

---

## 44. Wymagania ponownego uruchomienia

Niektóre aktualizacje pakietów i systemu mogą wymagać ponownego uruchomienia.

LUMS śledzi stan związany z ponownym uruchomieniem raportowany przez zarządzanego klienta.

Po aktualizacji systemu:

1. sprawdź raportowany stan ponownego uruchomienia
2. ustal, czy wymagane jest ponowne uruchomienie
3. wykonaj ponowne uruchomienie w odpowiednim oknie konserwacyjnym
4. pozwól Agentowi ponownie zaraportować
5. sprawdź, czy klient wrócił do normalnej pracy

Wymagania ponownego uruchomienia nie należy automatycznie interpretować jako awarii aktualizacji.

---

## 45. Operacyjna lista kontrolna aktualizacji

Dla rutynowej konserwacji pakietów:

```text
[ ] Wybrano właściwego klienta
[ ] Klient jest osiągalny
[ ] Sprawdzono bieżący stan oprogramowania
[ ] Sprawdzono dostępne aktualizacje
[ ] Wybrano właściwy pakiet/działanie
[ ] Sprawdzono wymagania konserwacyjne
[ ] Utworzono zadanie aktualizacji
[ ] Monitorowano wykonanie zadania
[ ] Zweryfikowano wynik zadania
[ ] Zweryfikowano zainstalowane oprogramowanie
[ ] Ponownie sprawdzono dostępne aktualizacje
[ ] Sprawdzono stan ponownego uruchomienia
[ ] W razie potrzeby przejrzano historię zadań
```

Operacja jest zakończona dopiero po zweryfikowaniu wynikowego stanu klienta.

---

## 46. Zasada zarządzania pakietami

LUMS zapewnia scentralizowaną orkiestrację i widoczność.

Zarządzany system operacyjny pozostaje odpowiedzialny za rzeczywiste zarządzanie pakietami.

Dlatego:

> **LUMS żąda operacji i śledzi ją. Natywny menedżer pakietów ją wykonuje.**

Ten podział pozwala LUMS zarządzać różnymi systemami Linux przy zachowaniu semantyki zarządzania pakietami każdego systemu operacyjnego.

## 47. Odzyskiwanie zadań

LUMS jest zaprojektowany do obsługi przerwanych zadań aktualizacji bez ślepego powtarzania operacji, które już zakończyły się pomyślnie.

Wykonywanie aktualizacji używa informacji punktów kontrolnych do śledzenia postępu.

Jest to szczególnie ważne, gdy:

* Agent zostanie przerwany
* klient uruchomi się ponownie
* serwer zostanie uruchomiony ponownie
* komunikacja sieciowa jest tymczasowo niedostępna
* operacja na pakiecie zakończy się przed zaraportowaniem wyniku

Mechanizm odzyskiwania używa zapisanego stanu zadania do określenia, jaka praca jeszcze wymaga wykonania.

---

## 48. Punkty kontrolne na poziomie pakietów

Zadania zawierające wiele operacji na pakietach są przetwarzane indywidualnie.

Pomyślna operacja na pakiecie jest zapisywana przed przejściem Agenta do następnej operacji.

Koncepcyjnie:

```text
Job
 │
 ├── Package A → SUCCESS
 │
 ├── Package B → SUCCESS
 │
 ├── Package C → interrupted
 │
 └── Package D → PENDING
```

Po odzyskaniu zakończone już operacje na pakietach nie powinny być niepotrzebnie wykonywane ponownie.

Pozostała praca może być następnie kontynuowana od zapisanego stanu.

Zmniejsza to ryzyko powtarzania operacji na pakietach po przerwaniu.

---

## 49. Przerwane zadania

Gdy zadanie aktualizacji zostanie przerwane, nie twórz natychmiast zadania zastępczego.

Najpierw ustal:

1. które zadanie zostało przerwane
2. która operacja na pakiecie była aktywna
3. które operacje na pakietach już się powiodły
4. czy menedżer pakietów zakończył operację
5. czy Agent automatycznie odzyskał zadanie
6. czy klient wymaga ponownego uruchomienia

Przed ręczną interwencją należy sprawdzić istniejącą historię zadań i logi Agenta.

---

## 50. Odzyskiwanie przez Agenta

Agent jest odpowiedzialny za kontynuowanie możliwej do odzyskania pracy po przerwaniu.

Odzyskiwanie powinno w miarę możliwości zachować pomyślne wyniki pakietów.

Jeśli operacja na pakiecie jest już zapisana jako pomyślna, odzyskiwanie nie może bezrefleksyjnie wykonać tej samej operacji ponownie.

Jeśli odzyskiwanie nie może bezpiecznie ustalić stanu operacji, warunek ten należy traktować jako problem operacyjny i zbadać go.

Nie zmieniaj ręcznie stanów zadań w bazie danych tylko po to, by zadanie wyglądało na zakończone.

---

## 51. Ponowne uruchomienie serwera podczas zadania

Ponowne uruchomienie serwera LUMS niekoniecznie oznacza, że operacja na pakiecie po stronie klienta została przerwana.

Serwer i klient mają oddzielne stany wykonania.

Po ponownym uruchomieniu serwera:

1. sprawdź, czy kontener LUMS jest uruchomiony
2. sprawdź dostępność bazy danych
3. sprawdź, czy klient może komunikować się z LUMS
4. sprawdź zadania aktualizacji, których to dotyczy
5. sprawdź raporty Agenta
6. zweryfikuj końcowy stan pakietów

Wynik wykonania po stronie klienta pozostaje ważnym źródłem prawdy dla operacji na pakiecie.

---

## 52. Ponowne uruchomienie klienta podczas zadania

Ponowne uruchomienie klienta może przerwać wykonanie Agenta lub wystąpić, ponieważ sama aktualizacja wymaga ponownego uruchomienia.

Te sytuacje należy rozróżnić.

### Oczekiwane ponowne uruchomienie

Aktualizacja zakończyła się i system wymaga ponownego uruchomienia.

### Nieoczekiwane przerwanie

System uruchomił się ponownie przed zakończeniem operacji lub przed zaraportowaniem wyniku.

Po powrocie klienta:

1. pozwól Agentowi uruchomić się normalnie
2. sprawdź komunikację z LUMS
3. sprawdź zadanie, którego to dotyczy
4. zweryfikuj stan pakietów
5. sprawdź status ponownego uruchomienia
6. pozwól odzyskiwaniu kontynuować, gdy ma zastosowanie

---

## 53. Wykrywanie ponownego uruchomienia

LUMS może śledzić wymagania ponownego uruchomienia raportowane przez zarządzanego klienta.

Wykrywanie ponownego uruchomienia nie jest tym samym co wykrywanie, czy maszyna jest obecnie osiągalna.

To są oddzielne stany:

```text
Client reachable
        │
        ├── reboot not required
        │
        └── reboot required

Client unreachable
        │
        └── current state cannot be confirmed
```

Administratorzy powinni więc unikać traktowania nieosiągalnego klienta jako dowodu, że wymagane jest ponowne uruchomienie.

---

## 54. Weryfikacja po ponownym uruchomieniu

Po wymaganym ponownym uruchomieniu:

1. poczekaj, aż system operacyjny będzie dostępny
2. sprawdź usługę lub timer Agenta
3. sprawdź uwierzytelnianie klienta
4. sprawdź raport klienta
5. sprawdź zadanie aktualizacji, którego to dotyczy
6. zweryfikuj zainstalowane wersje pakietów
7. zweryfikuj dostępne aktualizacje
8. sprawdź, czy wymagane jest kolejne ponowne uruchomienie

Ponowne uruchomienie należy uznać za operacyjnie zakończone dopiero po ponownym pomyślnym zaraportowaniu przez klienta.

---

## 55. Monitorowanie zadań aktualizacji

Administratorzy i Operatorzy powinni monitorować zadania podczas planowanej konserwacji.

Ważne stany obejmują:

| Stan      | Znaczenie                                  |
| --------- | ------------------------------------------ |
| `PENDING` | Zadanie istnieje, ale wykonanie nie rozpoczęło się |
| `RUNNING` | Wykonywanie zadania jest w toku            |
| `SUCCESS` | Wykonanie zakończyło się pomyślnie         |
| `FAILED`  | Wykonanie zakończyło się błędem            |

Stan zadania należy zawsze interpretować razem z informacjami o jego wyniku.

Na przykład zadanie `FAILED` należy zbadać na podstawie zapisanego wyniku, a nie po prostu ponowić.

---

## 56. Watcher wykonania

Agent LUMS zawiera dedykowany watcher wykonania.

Watcher jest odpowiedzialny za monitorowanie wykonywania zadań aktualizacji na kliencie.

Jego celem jest wspieranie niezawodnej obsługi wykonania niezależnie od przepływu raportowania.

Obecna wersja watchera to:

**Watcher 1.2.1**

Wersja Agenta to:

**Agent 1.7.0**

Te wersje należy zweryfikować po aktualizacjach klienta.

---

## 57. Monitorowanie watchera

Administratorzy mogą sprawdzić watcher przez systemd na zarządzanym kliencie.

Przydatne kontrole obejmują:

```bash
systemctl status lums-agent-watcher.service --no-pager
```

oraz:

```bash
journalctl -u lums-agent-watcher.service --no-pager -n 100
```

Timer można sprawdzić za pomocą:

```bash
systemctl status lums-agent-watcher.timer --no-pager
```

Dokładny stan aktywny/nieaktywny usługi oneshot należy interpretować razem z jej timerem i journalem.

Stan `inactive (dead)` nie jest automatycznie błędem dla usługi oneshot.

---

## 58. Timery raportowania i wykonywania

LUMS oddziela regularne raportowanie klienta od monitorowania wykonania.

Timer raportowania jest odpowiedzialny za zaplanowane uruchamianie Agenta.

Timer watchera jest odpowiedzialny za zaplanowane uruchamianie watchera.

Sprawdź oba podczas diagnozowania problemów z planowaniem po stronie klienta:

```bash
systemctl list-timers --all | grep lums-agent
```

Oczekiwane jednostki obejmują:

```text
lums-agent.timer
lums-agent-watcher.timer
```

Jeśli timer nie działa, sprawdź:

```bash
systemctl status lums-agent.timer --no-pager
systemctl status lums-agent-watcher.timer --no-pager
```

Następnie sprawdź odpowiednie wpisy journala.

---

## 59. Logowanie audytowe

LUMS zapisuje ważne działania administracyjne i istotne dla bezpieczeństwa działania aplikacji w logu audytowym.

Informacje audytowe mogą pomóc ustalić:

* która operacja wystąpiła
* który użytkownik ją zainicjował
* którego klienta dotyczyła
* kiedy operacja wystąpiła
* czy operacja została zaakceptowana
* jakie działanie administracyjne wykonano

Informacje audytowe należy traktować jako dowód operacyjny.

Nie należy ich lekceważąco usuwać ani modyfikować.

---

## 60. Administracyjne zdarzenia audytowe

Istotna aktywność administracyjna obejmuje operacje takie jak:

* tworzenie użytkownika
* przypisanie roli
* zarządzanie klientami
* rotacja tokenów
* tworzenie zadań aktualizacji
* operacje zarządzania pakietami
* zdarzenia bezpieczeństwa związane z uwierzytelnianiem

Dokładne dane zdarzenia zależą od operacji.

Administratorzy powinni używać informacji audytowych razem z historią zadań podczas badania nieoczekiwanej aktywności.

---

## 61. Obsługa logów audytowych

Logi audytowe należy obsługiwać ostrożnie.

Nie:

* modyfikuj historycznych wpisów audytowych, aby ukryć operację
* ujawniaj wrażliwych poświadczeń w eksportowanych logach
* publikuj logów zawierających tokeny klientów
* publikuj haseł ani materiału uwierzytelniającego
* kopiuj wrażliwych wyników logów do publicznych systemów zgłoszeń

Jeśli logi muszą być udostępnione do rozwiązywania problemów, najpierw zredaguj poświadczenia i inne wrażliwe informacje.

---

## 62. Logi aplikacji

Logi aplikacji opisują wewnętrzne działanie serwera LUMS.

Przydatne źródła obejmują:

```bash
sudo docker logs --tail 100 lums
```

Do monitorowania na żywo:

```bash
sudo docker logs -f lums
```

Podczas badania problemu w miarę możliwości zawęź okno czasowe.

Nie zrzucaj automatycznie całego logu produkcyjnego, gdy wystarczy mniejszy odpowiedni fragment.

---

## 63. Logi Agenta

Aktywność Agenta po stronie klienta można sprawdzić przez systemd:

```bash
journalctl -u lums-agent.service --no-pager -n 100
```

Dla aktywności watchera:

```bash
journalctl -u lums-agent-watcher.service --no-pager -n 100
```

Dla określonego okna czasowego można użyć filtrowania journala systemd.

Przykład:

```bash
journalctl -u lums-agent.service \
    --since "30 minutes ago" \
    --no-pager
```

Logi należy w miarę możliwości skorelować z ID affected job.

---

## 64. Korelacja logów

Podczas badania problemu z aktualizacją skoreluj informacje w całym systemie:

```text id="jv3j7c"
Interfejs webowy
  │
  ├── ID zadania
  │
  ▼
Log aplikacji / API LUMS
  │
  ▼
Zadanie aktualizacji
  │
  ▼
Agent
  │
  ▼
Natywny menedżer pakietów
```

Zapobiega to częstemu błędowi zakładania, że problem zaobserwowany w jednej warstwie powstał w tej samej warstwie.

---

## 65. Administracyjna lista kontrolna monitorowania

Podczas normalnej pracy okresowo sprawdzaj:

```text
[ ] Kontener LUMS jest uruchomiony
[ ] Endpoint HTTPS jest dostępny
[ ] Baza danych jest dostępna
[ ] Klienci raportują
[ ] Brak nieoczekiwanych nieudanych zadań
[ ] Brak niewyjaśnionych błędów uwierzytelniania
[ ] Timery Agenta są aktywne
[ ] Timery watchera są aktywne
[ ] Operacje menedżera pakietów kończą się normalnie
[ ] Aktywność audytowa jest dostępna
[ ] Logi nie zawierają niewyjaśnionych powtarzających się błędów
```

Częstotliwość tych kontroli powinna odpowiadać znaczeniu operacyjnemu wdrożenia LUMS.

---

## 66. Zasada odzyskiwania

Gdy wystąpi problem z aktualizacją, najbezpieczniejsze podejście administracyjne to:

```text
Obserwuj
   │
   ▼
Zidentyfikuj zadanie/klienta, którego dotyczy problem
   │
   ▼
Sprawdź stan i logi
   │
   ▼
Ustal rzeczywisty punkt awarii
   │
   ▼
Usuń podstawową przyczynę
   │
   ▼
Pozwól na odzyskanie lub ponów
   │
   ▼
Zweryfikuj końcowy stan
   │
   ▼
Udokumentuj istotne incydenty
```

Unikaj destrukcyjnych działań odzyskiwania, chyba że rzeczywisty stan awarii jest zrozumiały.

W szczególności nie usuwaj ręcznie zadań, rekordów bazy danych, blokad menedżera pakietów ani trwałych danych klienta tylko po to, by przywrócić czysto wyglądający interfejs.

> **Najpierw zachowaj dowody. Potem napraw stan. Na końcu zweryfikuj wynik.**

## 67. Administracja bazą danych

LUMS używa SQLite jako bazy danych aplikacji.

Baza danych produkcyjna jest przechowywana w trwałym wolumenie Docker:

```text
/var/lib/lums/lums.db
```

Baza danych jest trwała między zastąpieniami kontenera, o ile wolumen Docker jest zachowany.

Baza danych zawiera stan aplikacji, taki jak:

* użytkownicy
* zarządzani klienci
* zadania aktualizacji
* informacje o pakietach
* informacje audytowe
* stan związany z uwierzytelnianiem
* stan migracji

Administratorzy powinni traktować bazę danych jako krytyczne dane aplikacji.

---

## 68. Konfiguracja runtime SQLite

Obecna produkcyjna baza SQLite ma następujące ustawienia:

| Ustawienie     | Wartość                    |
| -------------- | -------------------------- |
| `journal_mode` | `wal`                      |
| `busy_timeout` | `5000`                     |
| `synchronous`  | `2`                        |
| `foreign_keys` | włączone przez aplikację   |

Aplikacja jawnie włącza egzekwowanie kluczy obcych SQLite dla połączeń z bazą danych.

Administratorzy nie powinni zmieniać tych ustawień bez zastanowienia.

Zmiany konfiguracji runtime bazy danych powinny być testowane przed wprowadzeniem do produkcji.

---

## 69. Integralność bazy danych

Integralność bazy danych należy sprawdzać, gdy pojawiają się oznaki uszkodzenia bazy danych lub nieoczekiwanego zachowania aplikacji.

Typowa kontrola integralności SQLite to:

```bash id="f0g8sl"
sudo docker exec lums \
    sqlite3 /var/lib/lums/lums.db \
    "PRAGMA integrity_check;"
```

Zdrowa baza danych powinna zwrócić:

```text
ok
```

Jeśli kontrola integralności zgłosi błędy, nie kontynuuj bezrefleksyjnej modyfikacji stanu aplikacji.

Zachowaj affected database i zbadaj przyczynę.

---

## 70. Migracje bazy danych

LUMS używa migracji aplikacji do wprowadzania zmian w bazie danych.

Migracje powinny być uruchamiane przez normalny mechanizm uruchamiania i migracji aplikacji.

Administratorzy nie powinni ręcznie modyfikować stanu migracji tylko po to, by obejść błąd.

Po aktualizacji aplikacji sprawdź:

1. kontener uruchamia się pomyślnie
2. migracje kończą się
3. aplikacja jest osiągalna
4. istniejący użytkownicy pozostają dostępni
5. istniejący klienci pozostają dostępni
6. istniejąca historia zadań pozostaje dostępna

---

## 71. Trwały wolumen Docker

Wolumen Docker zawierający dane aplikacji LUMS jest krytycznym trwałym zasobem.

Wolumen produkcyjny to:

```text
lums-data
```

Sprawdź go za pomocą:

```bash id="f3z2kd"
sudo docker volume inspect lums-data
```

Wolumen musi pozostać podłączony podczas zastępowania kontenera LUMS.

Usunięcie kontenera **nie** usuwa automatycznie wolumenu.

Usunięcie wolumenu powoduje jednak trwałe usunięcie trwałych danych aplikacji, chyba że istnieje osobna kopia zapasowa.

---

## 72. Administracja kontenerem

Aplikacja LUMS działa w utwardzonym kontenerze Docker.

Produkcyjna baza bezpieczeństwa obejmuje:

* użytkownika aplikacji innego niż root
* system plików głównych tylko do odczytu
* usunięte zdolności Linux
* `no-new-privileges`
* ograniczone tymczasowe systemy plików
* sekret montowany tylko do odczytu
* dedykowany trwały wolumen danych
* port aplikacji tylko na localhost

Kontenera nie należy uruchamiać ze słabszymi ustawieniami bezpieczeństwa tylko dlatego, że rozwiązywanie problemów staje się wygodniejsze.

---

## 73. Status kontenera

Sprawdź bieżący stan kontenera za pomocą:

```bash id="4n6p2v"
sudo docker ps --filter name=lums
```

Sprawdź pełną konfigurację runtime za pomocą:

```bash id="k1q4z8"
sudo docker inspect lums
```

Ważne właściwości obejmują:

* stan uruchomienia
* politykę restartu
* użytkownika
* system plików głównych tylko do odczytu
* zdolności
* opcje bezpieczeństwa
* powiązania portów
* montowania wolumenów

---

## 74. Weryfikacja bezpieczeństwa kontenera

Utwardzony runtime powinien nadal zapewniać oczekiwane właściwości.

Na przykład:

```bash id="0u7x3n"
sudo docker inspect lums \
    --format '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.Privileged}}'
```

Oczekiwana baza jest równoważna:

```text
lums true false
```

Zdolności powinny pozostać usunięte:

```bash id="k5n8ae"
sudo docker inspect lums \
    --format '{{json .HostConfig.CapDrop}}'
```

Oczekiwane:

```text
["ALL"]
```

Opcje bezpieczeństwa powinny obejmować:

```text
no-new-privileges:true
```

---

## 75. Port aplikacji

Aplikacja LUMS nasłuchuje na hoście przez interfejs loopback.

Oczekiwane mapowanie to:

```text
127.0.0.1:5050 → container:5000
```

Sprawdź je za pomocą:

```bash id="b6v2w0"
sudo docker port lums
```

Port aplikacji nie powinien być bezpośrednio wystawiony do LAN.

Dostęp zewnętrzny jest zapewniany przez Nginx przez HTTPS.

---

## 76. Nginx i HTTPS

Nginx zapewnia zewnętrzny punkt wejścia HTTPS dla LUMS.

Normalna ścieżka żądania to:

```text
Client Browser
      │
      ▼
HTTPS :443
      │
      ▼
Nginx
      │
      ▼
127.0.0.1:5050
      │
      ▼
LUMS Container
```

Port aplikacji Docker powinien pozostać powiązany z localhost.

Administratorzy powinni więc unikać wystawiania portu `5050` bezpośrednio przez firewall lub konfigurację Docker.

---

## 77. Weryfikacja HTTPS

Po zmianach w Nginx zawsze sprawdź konfigurację przed przeładowaniem:

```bash id="7f1h9m"
sudo nginx -t
```

Jeśli konfiguracja jest prawidłowa:

```bash id="4g5s2w"
sudo systemctl reload nginx
```

Następnie sprawdź HTTPS:

```bash id="2w8v6c"
curl -I https://LUMS-SERVER/
```

Zastąp `LUMS-SERVER` nazwą hosta objętą certyfikatem TLS serwera. Nie używaj `-k` do rutynowej weryfikacji; pomija ono walidację certyfikatu.

Pomyślna odpowiedź HTTPS potwierdza, że Nginx może połączyć się z aplikacją LUMS.

Walidację certyfikatu należy również przetestować przy użyciu nazwy hosta lub adresu, którego administratorzy normalnie używają.

Nie wyłączaj trwale weryfikacji certyfikatu za pomocą `-k`.

---

## 78. Przekierowanie HTTP

Endpoint HTTP powinien przekierowywać klientów do HTTPS.

Sprawdź:

```bash id="w5q0rx"
curl -I http://127.0.0.1/
```

Oczekiwane zachowanie to przekierowanie HTTP do endpointu HTTPS.

Dostęp administracyjny powinien używać HTTPS.

---

## 79. Konserwacja certyfikatu TLS

Certyfikaty TLS i klucze prywatne są zewnętrzne względem obrazu Docker.

Typowe lokalizacje to:

```text
/etc/lums/tls/lums.crt
/etc/lums/tls/lums.key
```

Klucze prywatne muszą pozostać chronione.

Przed zastąpieniem certyfikatu:

1. sprawdź nowy certyfikat
2. sprawdź pasujący klucz prywatny
3. sprawdź uprawnienia plików
4. zwaliduj konfigurację Nginx
5. przeładuj Nginx
6. sprawdź HTTPS
7. sprawdź logowanie do aplikacji

Nigdy nie umieszczaj prywatnych kluczy TLS w repozytorium Git ani w obrazie Docker.

---

## 80. Zarządzanie sekretami

Sekret aplikacji jest przechowywany poza obrazem kontenera.

Sekret produkcyjny jest montowany tylko do odczytu w kontenerze:

```text
/etc/lums/secrets/lums_secret
        │
        ▼
/run/secrets/lums_secret
```

Aplikacja otrzymuje sekret przez:

```text
LUMS_SECRET_KEY_FILE
```

Administratorzy nigdy nie mogą:

* zatwierdzać sekretu
* drukować sekretu
* umieszczać sekretu w dokumentacji
* ujawniać sekretu na zrzutach ekranu
* umieszczać sekretu w warstwie obrazu

Jeśli istnieje podejrzenie ujawnienia sekretu, traktuj go jako przejęty i postępuj zgodnie z odpowiednią procedurą rotacji sekretów.

---

## 81. Strategia kopii zapasowych

Dane LUMS należy kopiować zapasowo przed istotnymi zmianami administracyjnymi.

Należy co najmniej rozważyć ochronę:

* danych aplikacji SQLite
* konfiguracji aplikacji
* materiału TLS
* sekretów aplikacji
* informacji o konfiguracji klientów
* odpowiedniej dokumentacji operacyjnej

Kopie zapasowe należy przechowywać oddzielnie od kontenera produkcyjnego i jego trwałego wolumenu Docker.

Kopia zapasowa istniejąca tylko na tym samym hoście lub w tym samym wolumenie Docker nie zapewnia odpowiedniej ochrony przed utratą tego hosta lub wolumenu.

---

## 82. Kopia zapasowa bazy danych

Bazę danych SQLite należy kopiować zapasowo metodą świadomą SQLite, a nie przez proste skopiowanie aktywnie modyfikowanego pliku bazy danych bez uwzględnienia jego stanu.

Przed wykonaniem kopii zapasowej:

1. zidentyfikuj produkcyjną bazę danych
2. upewnij się, że miejsce docelowe kopii zapasowej jest dostępne
3. utwórz kopię zapasową przy użyciu odpowiedniej metody bezpiecznej dla SQLite
4. sprawdź, czy kopia zapasowa istnieje
5. zapisz, kiedy została utworzona

Nie zakładaj, że pomyślne skopiowanie pliku automatycznie oznacza, że istnieje prawidłowa, odtwarzalna kopia zapasowa bazy danych.

---

## 83. Weryfikacja kopii zapasowej

Kopia zapasowa nie jest uznawana za niezawodną, dopóki nie zostanie przetestowana.

Okresowo sprawdzaj, czy kopię zapasową można:

* odczytać
* otworzyć jako dane SQLite
* sprawdzić pod kątem integralności
* przywrócić w izolowanym środowisku testowym

Na przykład wyodrębnioną kopię testową można sprawdzić za pomocą:

```bash id="p3v7cx"
sqlite3 /path/to/test-copy.db \
    "PRAGMA integrity_check;"
```

Oczekiwany wynik:

```text
ok
```

Produkcyjnej kopii zapasowej nigdy nie należy testować przez nadpisanie aktywnej produkcyjnej bazy danych.

---

## 84. Zasada przywracania

Przywracanie jest kontrolowaną operacją administracyjną.

Przed przywróceniem:

1. zidentyfikuj właściwą kopię zapasową
2. zweryfikuj jej integralność
3. ustal wymagany punkt odzyskiwania
4. w odpowiedni sposób zatrzymaj lub odizoluj aktywność aplikacji
5. zachowaj bieżący stan produkcyjny
6. przywróć kopię zapasową
7. zweryfikuj integralność bazy danych
8. uruchom aplikację
9. zweryfikuj migracje
10. zweryfikuj użytkowników i klientów
11. zweryfikuj historię zadań
12. zweryfikuj normalne raportowanie klientów

Nie nadpisuj jedynej kopii produkcyjnej bazy danych podczas odzyskiwania.

---

## 85. Weryfikacja przywracania

Po przywróceniu sprawdź co najmniej:

```text id="q6r2yh"
[ ] Kontener uruchamia się
[ ] Baza danych otwiera się
[ ] Kontrola integralności SQLite przechodzi
[ ] Użytkownicy są obecni
[ ] Role są poprawne
[ ] Klienci są obecni
[ ] Uwierzytelnianie klientów działa
[ ] Historia zadań jest obecna
[ ] Informacje audytowe są dostępne
[ ] HTTPS działa
[ ] Klienci mogą raportować
[ ] Nowe operacje mogą być tworzone
```

Przywracanie jest zakończone dopiero po zweryfikowaniu aplikacji i jej zarządzanych klientów.

---

## 86. Zasada kopii zapasowych serwera

Najważniejsza zasada administracyjna dla trwałych danych LUMS to:

> **Nigdy nie wykonuj destrukcyjnej operacji na bazie danych lub wolumenie bez zweryfikowanej ścieżki odzyskiwania.**

W szczególności nie usuwaj `lums-data` tylko dlatego, że kontener jest przebudowywany lub zastępowany.

Zastąpienie kontenera i usunięcie trwałych danych to oddzielne operacje.

---

## 87. Administracyjna lista kontrolna serwera

Przed wprowadzeniem istotnej zmiany po stronie serwera:

```text id="7h3m0p"
[ ] Zapisano bieżący stan kontenera
[ ] Zapisano bieżący obraz
[ ] Dostępna jest kopia zapasowa bazy danych
[ ] Zweryfikowano integralność kopii zapasowej
[ ] Sprawdzono aktywne zadania
[ ] Sprawdzono stan raportowania klientów
[ ] Udokumentowano zmiany konfiguracji
[ ] Materiał TLS jest dostępny
[ ] Zweryfikowano obsługę sekretów
[ ] Znana jest ścieżka wycofania
```

Dopiero po uwzględnieniu tych warunków należy kontynuować istotną zmianę produkcyjną.

---

## 88. Zasada administracji serwerem

LUMS oddziela stan aplikacji od jednorazowego kontenera aplikacji.

```text
Disposable
└── LUMS Container

Persistent
├── SQLite Database
└── lums-data Volume

External
├── TLS Material
└── Application Secret
```

Ten podział pozwala zastąpić kontener aplikacji bez celowego niszczenia trwałych danych aplikacji.

> **Zastępuj aplikację, gdy to konieczne. Zachowuj dane, chyba że usunięcie danych jest wyraźnie zamierzone.**

## 89. Rutynowa konserwacja

Rutynowa konserwacja utrzymuje niezawodność instalacji LUMS i zmniejsza ryzyko nieoczekiwanych problemów operacyjnych.

Typowe działania konserwacyjne obejmują:

* przeglądanie nieudanych zadań aktualizacji
* sprawdzanie raportowania klientów
* przeglądanie logów aplikacji
* przeglądanie aktywności audytowej
* weryfikację kopii zapasowych
* sprawdzanie dostępnego miejsca na dysku
* przeglądanie stanu kontenera Docker
* sprawdzanie ważności certyfikatu TLS
* przeglądanie aktualizacji bezpieczeństwa
* weryfikację bieżącej wersji LUMS i obrazu

Konserwację należy wykonywać w odpowiednim oknie konserwacyjnym, gdy zmiany mogą wpływać na produkcyjnych klientów.

---

## 90. Konserwacja przed zmianami

Przed wykonaniem konserwacji, która może wpłynąć na serwer LUMS:

1. przejrzyj aktywne zadania aktualizacji
2. sprawdź, czy klienci nie przechodzą nieoczekiwanej konserwacji
3. utwórz lub zweryfikuj bieżącą kopię zapasową
4. zapisz bieżący stan kontenera i obrazu
5. udokumentuj planowaną zmianę
6. upewnij się, że istnieje ścieżka wycofania

Nie rozpoczynaj konserwacji od natychmiastowego zatrzymania lub usunięcia komponentów produkcyjnych.

Najpierw ustal bieżący stan.

---

## 91. Konserwacja obrazu Docker

Obrazy aplikacji LUMS należy przebudowywać z sprawdzonego drzewa źródłowego.

Przed zbudowaniem nowego obrazu:

```bash id="x0m7r4"
cd /opt/lums-public
```

Uruchom automatyczny zestaw testów:

```bash id="4gk1dp"
./.venv-test/bin/pytest -q
```

Kontynuuj tylko wtedy, gdy wynik testów jest zrozumiały.

Zbuduj nowy obraz przy użyciu odrębnego tymczasowego tagu:

```bash id="m8q3vz"
sudo docker build -t lums:new .
```

Tymczasowy tag pozwala zidentyfikować aktualnie uruchomiony obraz podczas procesu zastępowania.

---

## 92. Weryfikacja obrazu

Po zbudowaniu nowego obrazu sprawdź, czy obraz istnieje:

```bash id="h6s2we"
sudo docker image inspect lums:new
```

Przejrzyj konfigurację obrazu przed wdrożeniem.

W odpowiednich przypadkach sprawdź:

* digest obrazu
* obraz bazowy
* pliki aplikacji
* zainstalowane zależności
* rozmiar obrazu
* wystawione porty
* skonfigurowanego użytkownika

Obraz należy wdrożyć dopiero po przejrzeniu wyników budowania i testów.

---

## 93. Kontrolowane zastąpienie kontenera

Zastąpienie kontenera należy wykonywać celowo.

Przed zastąpieniem produkcyjnego kontenera:

```text id="m3z8qk"
[ ] Testy przeszły
[ ] Nowy obraz istnieje
[ ] Dostępna jest kopia zapasowa bazy danych
[ ] Sprawdzono aktywne zadania
[ ] Zapisano bieżący obraz
[ ] Potwierdzono trwały wolumen
[ ] Sekret jest dostępny
[ ] Konfiguracja TLS jest dostępna
[ ] Zidentyfikowano obraz do wycofania
```

Przed uruchomieniem przykładu porównaj go z rzeczywistym działającym kontenerem. Poniższe
wartości są przykładem, a nie poleceniem bezpiecznym dla każdej instalacji.
W szczególności źródłowe ścieżki montowania bind w Docker po lewej stronie `:` muszą
odpowiadać Twojemu hostowi, a stary kontener może mieć inną nazwę.

Wyświetl obraz, montowania, opublikowane porty, politykę restartu i ustawienia utwardzania
bez drukowania wartości zmiennych środowiskowych:

```bash
sudo docker inspect lums --format 'Image={{.Config.Image}}
Mounts={{json .Mounts}}
Ports={{json .HostConfig.PortBindings}}
Restart={{json .HostConfig.RestartPolicy}}
Readonly={{.HostConfig.ReadonlyRootfs}}
CapDrop={{json .HostConfig.CapDrop}}
SecurityOpt={{json .HostConfig.SecurityOpt}}
Tmpfs={{json .HostConfig.Tmpfs}}'
```

Zapisz wynik w prywatnym miejscu i użyj go do sprawdzenia, czy nowy kontener
zachowuje ten sam wolumen bazy danych, plik sekretu, katalog kopii zapasowych, powiązanie portu tylko lokalnie
i opcje bezpieczeństwa. Nie wklejaj treści sekretów ani wartości zmiennych środowiskowych
do notatek lub wiadomości.

Zatrzymaj istniejący kontener dopiero po uwzględnieniu tych warunków.

Produkcyjny kontener powinien zachować utwardzoną konfigurację runtime.

Przykład:

```bash id="n8q2kf"
sudo docker stop lums
sudo docker rename lums lums-before-upgrade
```

Następnie uruchom nowy obraz z ustaloną utwardzoną konfiguracją:

```bash id="c7w4md"
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
    -v /var/backups/lums:/var/backups/lums \
    -e LUMS_SECRET_KEY_FILE=/run/secrets/lums_secret \
    -e LUMS_BACKUP_DIR=/var/backups/lums \
    lums:new
```

Nie usuwaj `lums-before-upgrade`, dopóki nowe wdrożenie nie zostanie zwalidowane.

---

## 94. Walidacja po aktualizacji

Natychmiast po zastąpieniu kontenera sprawdź:

```bash id="b4m7tz"
sudo docker ps --filter name=lums
```

Następnie sprawdź logi:

```bash id="v5n2ra"
sudo docker logs --tail 100 lums
```

Sprawdź HTTPS:

```bash id="w9x1kf"
curl -I https://LUMS-SERVER/
```

Zastąp `LUMS-SERVER` nazwą hosta objętą certyfikatem TLS serwera. Nie używaj `-k` do rutynowej weryfikacji; pomija ono walidację certyfikatu.

Następnie sprawdź aplikację przez normalny interfejs administracyjny.

Sprawdź, czy istniejący użytkownicy, klienci i ostatnia historia nadal są obecni.
Przejrzyj logi pod kątem błędów uruchamiania lub migracji. Działający kontener sam w sobie
nie dowodzi, że aplikacja lub jej baza danych są zdrowe.

### Wycofanie, jeśli nowy kontener nie działa

Zachowaj stary kontener, dopóki nowa wersja nie przejdzie walidacji. Jeśli
nowy kontener jest bezużyteczny i potwierdzono, że stary kontener nazywa się
`lums-before-upgrade`, zatrzymaj i usuń **tylko nowy kontener**, a następnie
zmień nazwę i uruchom ponownie stary:

```bash
sudo docker stop lums
sudo docker rm lums
sudo docker rename lums-before-upgrade lums
sudo docker start lums
```

`docker rm lums` bez `-v` usuwa kontener, a nie wolumen `lums-data`.
Nigdy nie dodawaj `-v` do tego polecenia wycofania. Jeśli nazwa kontenera się różni
lub nie masz pewności, który kontener jest stary, a który nowy, nie uruchamiaj tych
poleceń; sprawdź bieżący stan lub poproś administratora o pomoc. Po
wycofaniu sprawdź logi i zweryfikuj, czy interfejs webowy i dane są
dostępne.

---

## 95. Trwałe dane po aktualizacji

Zastąpienie kontenera nie może usuwać trwałego wolumenu Docker.

Sprawdź:

```bash id="j4p8sx"
sudo docker inspect lums \
    --format '{{json .Mounts}}'
```

Potwierdź, że:

```text id="m7z3kc"
/var/lib/lums
```

jest oparte na oczekiwanym trwałym wolumenie.

Następnie sprawdź:

* użytkownicy nadal istnieją
* role pozostają poprawne
* klienci pozostają zarejestrowani
* historia zadań pozostaje dostępna
* informacje audytowe pozostają dostępne
* migracje zakończyły się pomyślnie

---

## 96. Baza bezpieczeństwa po aktualizacji

Po wdrożeniu nowego obrazu ponownie sprawdź utwardzony runtime.

Sprawdź:

```bash id="q6c3xv"
sudo docker inspect lums \
    --format '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}} {{.HostConfig.Privileged}}'
```

Oczekiwana baza:

```text id="s0r8jm"
lums true false
```

Sprawdź również:

```text id="g4m2vx"
CapDrop = ALL
SecurityOpt = no-new-privileges:true
```

oraz że:

```text id="c3p9rw"
127.0.0.1:5050 → container:5000
```

pozostaje ekspozycją aplikacji.

Pomyślna aktualizacja aplikacji nie może po cichu osłabić bazy bezpieczeństwa.

---

## 97. Komunikacja klientów po aktualizacji

Po aktualizacji serwera sprawdź, czy zarządzani klienci nadal mogą się komunikować.

Najpierw sprawdź co najmniej jednego reprezentatywnego klienta.

Sprawdź:

```text id="x8h5qk"
[ ] Uwierzytelnianie klienta kończy się sukcesem
[ ] Raport klienta jest akceptowany
[ ] Zainstalowane oprogramowanie jest dostępne
[ ] Dostępne aktualizacje są dostępne
[ ] Zadania aktualizacji mogą być tworzone
[ ] Wyniki Agenta są akceptowane
```

Jeśli wdrożono wiele platform klienckich, sprawdź reprezentatywne systemy z każdej obsługiwanej platformy.

---

## 98. Wykonywanie aktualizacji po aktualizacji

Nie wykonuj natychmiast dużej aktualizacji produkcyjnej po zastąpieniu serwera LUMS.

Najpierw wykonaj kontrolowany test funkcjonalny.

Odpowiedni test powinien zweryfikować pełną ścieżkę:

```text id="y7k2fd"
Web UI
  ↓
API
  ↓
Update Job
  ↓
Agent
  ↓
Package Manager
  ↓
Result
  ↓
Database
  ↓
Web UI
```

Dopiero po pomyślnym zakończeniu kontrolowanego testu należy wznowić normalne operacje konserwacyjne.

---

## 99. Wycofanie

Wycofanie powinno być możliwe, gdy nowy obraz powoduje nieoczekiwany problem produkcyjny.

Zachowaj:

* poprzedni działający obraz
* trwałe dane
* kopię zapasową bazy danych
* poprzednią konfigurację
* poprzedni materiał TLS
* odpowiednie logi

Jeśli nowy kontener nie jest użyteczny:

1. zatrzymaj nowy kontener
2. w miarę możliwości zachowaj go do zbadania
3. zatrzymaj dalsze zmiany administracyjne
4. przywróć poprzedni znany jako dobry obraz
5. użyj ponownie istniejącego trwałego wolumenu
6. uruchom utwardzony runtime
7. sprawdź aplikację
8. sprawdź klientów
9. sprawdź stan zadań
10. zbadaj nieudany obraz osobno

Nie usuwaj trwałego wolumenu w ramach normalnego wycofania.

---

## 100. Walidacja wycofania

Po wycofaniu sprawdź:

```text id="z1j8md"
[ ] LUMS uruchamia się
[ ] HTTPS działa
[ ] Użytkownicy mogą się uwierzytelnić
[ ] Role są poprawne
[ ] Klienci są obecni
[ ] Uwierzytelnianie klientów działa
[ ] Historia zadań jest dostępna
[ ] Informacje audytowe są dostępne
[ ] Inwentarz pakietów jest dostępny
[ ] Zadania aktualizacji mogą być śledzone
[ ] Baza bezpieczeństwa jest nienaruszona
```

Wycofanie jest zakończone dopiero po zweryfikowaniu aplikacji i ścieżki komunikacji z klientami.

---

## 101. Administracja awaryjna

Administracja awaryjna powinna w miarę możliwości zachowywać dowody i trwały stan.

Przykłady obejmują:

* powtarzające się awarie aplikacji
* błędy integralności bazy danych
* szeroko rozpowszechnione błędy uwierzytelniania klientów
* nieoczekiwane zachowanie zadań pakietów
* podejrzenie ujawnienia poświadczeń
* uszkodzone aktualizacje
* awarie TLS wpływające na wszystkich użytkowników

Preferowana kolejność to:

```text id="f8k3wz"
Zachowaj
   ↓
Obserwuj
   ↓
Izoluj
   ↓
Odzyskaj
   ↓
Zweryfikuj
   ↓
Udokumentuj
```

Unikaj usuwania logów, baz danych, kontenerów lub rekordów klientów tylko dlatego, że wydają się częścią problemu.

---

## 102. Zasada zmian administracyjnych

Każda istotna zmiana produkcyjna powinna mieć trzy jasno zdefiniowane stany:

### Przed

Bieżący stan produkcyjny jest znany i odtwarzalny.

### W trakcie

Zmiana jest wykonywana zgodnie z udokumentowaną procedurą.

### Po

Wynikowy stan jest weryfikowany względem oczekiwanej bazy.

Dzięki temu praca administracyjna jest powtarzalna i zmniejsza ryzyko przypadkowego dryfu konfiguracji.

---

## 103. Kontrolowana deinstalacja

Deinstalacja jest destrukcyjną operacją administracyjną.

Należy ją wykonać tylko wtedy, gdy wdrożenie LUMS jest celowo usuwane.

Przed usunięciem LUMS:

```text id="u5r2nc"
[ ] Zidentyfikowano wszystkich zarządzanych klientów
[ ] Sprawdzono aktywne zadania aktualizacji
[ ] Wyeksportowano lub zachowano wymaganą historię zadań
[ ] Zachowano wymagane informacje audytowe
[ ] Utworzono kopię zapasową bazy danych
[ ] Zweryfikowano kopię zapasową
[ ] W razie potrzeby zachowano materiał TLS
[ ] W razie potrzeby zachowano sekret aplikacji
[ ] Zachowano dokumentację
[ ] Udokumentowano wymagania ponownej instalacji
```

Nie usuwaj trwałych danych przed potwierdzeniem, że nie są już wymagane.

---

## 104. Usuwanie kontenera

Aby usunąć kontener aplikacji po wycofaniu wdrożenia z eksploatacji:

```bash id="n2x7kc"
sudo docker stop lums
sudo docker rm lums
```

Wolumen Docker celowo **nie** jest usuwany przez te polecenia.

Pozwala to zachować dane aplikacji do późniejszej inspekcji lub odzyskiwania.

---

## 105. Usuwanie trwałych danych

Usunięcie wolumenu Docker LUMS jest oddzielną destrukcyjną operacją.

Wykonaj ją tylko po potwierdzeniu, że baza danych i cały przechowywany stan aplikacji nie są już wymagane.

Przykład:

```bash id="r8w3mz"
sudo docker volume rm lums-data
```

To trwale usuwa trwałe dane aplikacji przechowywane w tym wolumenie.

Nie wykonuj tego polecenia podczas normalnej aktualizacji ani wycofania.

---

## 106. Usuwanie komponentów klienta

Gdy zarządzany klient jest trwale usuwany z LUMS, odinstaluj lub wyłącz jego komponenty Agenta zgodnie z procedurą systemu operacyjnego klienta.

Klient nie powinien już raportować do serwera LUMS po wycofaniu z eksploatacji.

Jeśli wymagane są zapisy historyczne, przed usunięciem klienta zachowaj odpowiednie informacje o zadaniach i informacje audytowe.

---

## 107. Końcowa lista kontrolna administracji

### Administracja użytkownikami

```text id="p5z8cv"
[ ] Użytkownicy mają odpowiednie role
[ ] Dostęp Administratora jest ograniczony
[ ] Wyłączone konta są przeglądane
[ ] Poświadczenia są chronione
```

### Administracja klientami

```text id="q2m7xd"
[ ] Klienci są poprawnie zarejestrowani
[ ] Tokeny klientów są chronione
[ ] Wyłączeni klienci są przeglądani
[ ] Rotacja tokenów jest wykonywana, gdy wymagana
[ ] Raportowanie klientów jest zdrowe
```

### Administracja aktualizacjami

```text id="h6v9kt"
[ ] Dostępne aktualizacje są przeglądane
[ ] Zadania aktualizacji są monitorowane
[ ] Nieudane zadania są badane
[ ] Operacje na pakietach są weryfikowane
[ ] Wymagania ponownego uruchomienia są sprawdzane
[ ] Historia zadań jest zachowywana
```

### Administracja serwerem

```text id="r3c8wn"
[ ] Kontener jest uruchomiony
[ ] Trwały wolumen jest podłączony
[ ] Integralność SQLite jest zdrowa
[ ] HTTPS działa
[ ] Materiał TLS jest prawidłowy
[ ] Sekret aplikacji jest chroniony
[ ] Kopie zapasowe są dostępne
```

### Bezpieczeństwo

```text id="v7m4qx"
[ ] RBAC pozostaje egzekwowane
[ ] Ograniczenia Viewera pozostają nienaruszone
[ ] Uwierzytelnianie klientów działa
[ ] Kontener pozostaje utwardzony
[ ] Port aplikacji pozostaje tylko na localhost
[ ] Żadne poświadczenia nie są ujawnione
[ ] Logi nie zawierają niewyjaśnionych wrażliwych informacji
```

---

## 108. Baza operacyjna

Zdrowa instalacja LUMS powinna spełniać następującą bazę:

```text id="d4k9sy"
Application
    ├── HTTPS available
    ├── Authentication available
    └── RBAC enforced

Server
    ├── Hardened container
    ├── Persistent database
    └── Valid migrations

Clients
    ├── Authenticated
    ├── Reporting
    ├── Software inventory available
    └── Update information available

Operations
    ├── Update jobs executable
    ├── Results recorded
    ├── Recovery supported
    └── Reboot state reported

Security
    ├── Secrets protected
    ├── Tokens protected
    ├── Audit information retained
    └── Network exposure restricted

Recovery
    ├── Backups available
    ├── Restore path known
    └── Rollback path known
```

---

## 109. Administracja zakończona

Administracja LUMS powinna zawsze priorytetowo traktować kontrolowane, obserwowalne i odwracalne zmiany.

Cykl życia administracji to:

```text id="w6f1pa"
Plan
  ↓
Observe
  ↓
Change
  ↓
Verify
  ↓
Document
  ↓
Maintain
```

Najważniejsze zasady operacyjne to:

> **Stosuj najmniejsze konieczne uprawnienia.**

> **Zachowuj dane trwałe.**

> **Nie zmieniaj stanu bez zrozumienia stanu bieżącego.**

> **Weryfikuj wynik każdej istotnej operacji.**

> **Utrzymuj przetestowaną ścieżkę odzyskiwania.**

Procedury instalacji znajdują się w `install.md`.

Architektura bezpieczeństwa i wyniki audytu znajdują się w `security.md`.

Procedury diagnozy i odzyskiwania znajdują się w `troubleshooting.md`.

---

## 110. Końcowa zasada administracji

LUMS ma na celu uczynienie zarządzania aktualizacjami Linuksa przewidywalnym i obserwowalnym.

Praca administracyjna nie powinna więc opierać się na założeniach ani ślepym powtarzaniu.

Gdy coś się zmienia:

**Najpierw obserwuj. Potem zmieniaj. Na końcu weryfikuj.**

Gdy coś się psuje:

**Zachowaj dowody. Zidentyfikuj warstwę awarii. Odzyskuj świadomie.**

Gdy coś działa:

**Zapisz wynik i zachowaj znaną jako dobrą bazę.**
