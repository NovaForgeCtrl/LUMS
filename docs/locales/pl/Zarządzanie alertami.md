# Zarządzanie alertami LUMS: bieżąca implementacja

Ta notatka opisuje kod zarządzania alertami obecny w LUMS. Jest to dokumentacja kodu, a nie plan rozwoju funkcji ani obietnica, że wszystkie widoczne elementy interfejsu działają. Implementacja koncentruje się w plikach `server/alerts.py` i `server/alerts_routes.py`.

## Zaimplementowane funkcje

LUMS przechowuje w SQLite reguły alertów, rekordy alertów i historię ich stanów. Blueprint Flask tworzy dla każdego żądania instancję `AlertManager` korzystającą z fabryki połączeń z bazą danych aplikacji. Przy każdym żądaniu menedżer wczytuje z bazy reguły i nierozwiązane alerty.

Obecne API umożliwia:

- wyświetlanie, tworzenie, aktualizowanie i usuwanie reguł alertów;
- ręczne wyzwolenie alertu dla istniejącej, włączonej reguły;
- przeglądanie aktywnych alertów i stronicowanej historii;
- potwierdzanie, rozwiązywanie i ręczne eskalowanie aktywnego alertu.

Wartości ważności alertu to `critical`, `warning` i `info`. Przechowywane stany alertu to `triggered`, `acknowledged`, `resolved` i `escalated`. Zmiany potwierdzenia, rozwiązania i eskalacji są zapisywane w `alert_history`. Rozwiązane alerty są usuwane z kolekcji aktywnych alertów menedżera, ale pozostają w bazie danych.

## Ważne ograniczenia

Model reguły przechowuje warunek, próg, ważność, ścieżkę eskalacji oraz flagi grupowania i deduplikacji. Obecny serwer **nie** sprawdza warunków na podstawie telemetrii ani innych pomiarów. Reguły nie wyzwalają alertów automatycznie: uwierzytelniony podmiot musi wywołać `POST /alerts/trigger`.

Podczas ręcznego wyzwolenia alertu menedżer może wywołać dostawców wskazanych w jego ścieżce eskalacji. Aplikacja webowa tworzy jednak menedżery z pustą mapą dostawców, a endpointy integracji nie pozwalają ich skonfigurować; dlatego wyzwolenie z aplikacji webowej nie zapewnia dostarczania powiadomień. Wartości grupowania i deduplikacji są jedynie przechowywane, ale nie są stosowane.

`AlertManager` definiuje klasy dostawców poczty elektronicznej, Slacka, PagerDuty i ogólnych webhooków, ale aplikacja ich nie konfiguruje. API integracji celowo informuje, że integracje są niedostępne, i zwraca `501 Not Implemented` dla żądań konfiguracji, testowania i usuwania. Nie należy oczekiwać dostarczania powiadomień. `POST /alerts/clear-all` również zwraca `501`, aby uniemożliwić usunięcie historii alertów przez ten endpoint.

Strona `/alerts/` to podstawowy widok renderowany po stronie serwera. Kontrolki kart reguł, historii i integracji oraz przyciski działań na alertach nie tworzą kompletnego, interaktywnego interfejsu zarządzania. Źródłem prawdy jest udokumentowane zachowanie API; nie zakładaj, że widoczny przycisk wykonuje działanie. Obecna implementacja nie zapewnia aktualizacji w czasie rzeczywistym przez push ani WebSocket.

## Trasy i kontrola dostępu

Wszystkie trasy wymagają uwierzytelnionej sesji webowej.

| Metoda | Trasa | Uprawnienie | Bieżące działanie |
| --- | --- | --- | --- |
| `GET` | `/alerts/` | `alerts.view` | Renderuje podstawowy widok alertów |
| `GET` | `/alerts/rules` | `alerts.view` | Wyświetla zapisane reguły |
| `POST` | `/alerts/rules` | `alerts.manage` | Tworzy zweryfikowaną regułę |
| `PUT` | `/alerts/rules/<rule_id>` | `alerts.manage` | Aktualizuje zapisaną regułę |
| `DELETE` | `/alerts/rules/<rule_id>` | `alerts.manage` | Usuwa regułę, jeśli pozwalają na to ograniczenia bazy danych |
| `GET` | `/alerts/current` | `alerts.view` | Zwraca aktywne alerty |
| `GET` | `/alerts/history` | `alerts.view` | Zwraca historię alertów |
| `POST` | `/alerts/trigger` | `alerts.manage` | Ręcznie tworzy alert dla włączonej reguły |
| `POST` | `/alerts/<alert_id>/acknowledge` | `alerts.manage` | Zapisuje potwierdzenie |
| `POST` | `/alerts/<alert_id>/resolve` | `alerts.manage` | Rozwiązuje aktywny alert |
| `POST` | `/alerts/<alert_id>/escalate` | `alerts.manage` | Ręcznie zwiększa licznik eskalacji |
| `POST` | `/alerts/clear-all` | `alerts.manage` | Wyłączona; zwraca `501` |
| `GET` | `/alerts/integrations` | `alerts.view` | Zwraca pustą listę i `available: false` |
| `POST` / `DELETE` | `/alerts/integrations/...` | `alerts.manage` | Wyłączone; zwracają `501` |

Trasy zmieniające stan wymagają ochrony CSRF oraz odpowiedniego uprawnienia. Kontrola uprawnień jest egzekwowana na serwerze. `alerts.manage` zależy od `alerts.view`; przypisania uprawnień do ról są utrzymywane przez migrację zabezpieczeń i konfigurację uprawnień.

## Trwałe tabele

Podczas tworzenia `AlertManager` inicjalizuje następujące tabele:

- `alert_rules`: definicje reguł i ich skonfigurowane wartości;
- `alerts`: rekordy alertów i ich bieżący stan cyklu życia;
- `alert_history`: historia potwierdzeń, rozwiązań i eskalacji;
- `notification_integrations`: zarezerwowany schemat konfiguracji integracji;
- `alert_notifications_log`: zarezerwowany schemat dziennika dostarczania.

Dwie ostatnie tabele nie oznaczają, że integracje są dostępne. Endpointy HTTP integracji pozostają wyłączone do czasu wdrożenia bezpiecznej trwałej konfiguracji i obsługi dostarczania powiadomień.

## Weryfikacja

Trasy alertów, egzekwowanie uprawnień, walidacja ładunku, trwałość danych i obsługa cyklu życia są objęte testami `tests/test_alerts.py`. Uruchom odpowiednie testy ponownie dla wdrażanej rewizji. Pomyślne testy nie sprawiają, że wyłączone endpointy integracji lub nieweryfikowane reguły stają się dostępnymi funkcjami.

## Powiązany kod

- `server/alerts.py`
- `server/alerts_routes.py`
- `server/security.py`
- `server/security_migration.py`
- `tests/test_alerts.py`
