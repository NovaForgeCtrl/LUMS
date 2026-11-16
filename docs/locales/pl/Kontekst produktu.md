# Produkt

## Platforma

Web.

## Użytkownicy

Administratorzy systemów Linux i zespoły IT odpowiedzialne za centralne zarządzanie wieloma systemami Linux i ich aktualizowanie. Produkt powinien być również odpowiedni dla pojedynczego administratora, małego zespołu IT oraz właściwych środowisk usług zarządzanych.

## Cel produktu

LUMS zapewnia centralny widok zarządzanych klientów, zainstalowanego oprogramowania, dostępnych aktualizacji i wykonywania zadań aktualizacji. Pomaga administratorom świadomie rozpoczynać działania i weryfikować ich wynik, zamiast bezrefleksyjnie stosować aktualizacje we wszystkich systemach.

## Kontekst operacyjny

W codziennej pracy administratorzy używają LUMS do sprawdzania stanu floty, telemetrii, oprogramowania i aktualizacji; uruchamiania ukierunkowanych zadań aktualizacji; przeglądania historii wykonania; oraz zarządzania dostępem użytkowników, zapisami audytowymi i kopiami zapasowymi bazy danych. Topologia infrastruktury może łączyć zarejestrowanych klientów LUMS z systemami i relacjami utrzymywanymi ręcznie.

## Możliwości i ograniczenia

- Kontrola dostępu oparta na rolach i uprawnieniach, rejestrowanie audytu, kopie zapasowe bazy danych, widoczność pakietów i zadania aktualizacji klientów to podstawowe możliwości operacyjne.
- Operacje aktualizacji systemu muszą być kontrolowane, podlegać audytowi i rzetelnie zgłaszać błędy; nie należy oznaczać aktualizacji jako udanej, jeśli jej kontrole nie zakończyły się powodzeniem.
- Zarejestrowani klienci i przekazywane przez nich dane są dostępnym źródłem automatycznie importowanego inwentarza infrastruktury. Dodatkowa infrastruktura i relacje wymagają jawnego ręcznego wprowadzenia, chyba że potwierdzono przyszłą integrację.
- Edytowanie inwentarza infrastruktury jest ograniczone do administratorów.
- Nie należy sugerować automatycznego wykrywania dowolnych maszyn wirtualnych, kontenerów, urządzeń sieciowych ani zależności.

## Zobowiązania dotyczące marki

- Zachować nazwę LUMS i istniejące logo.
- Użytkownik wyraźnie nazywa motyw stadionowy „LUMS-Stadion” i poprosił o użycie istniejącego obrazu tła stadionu w panelu stanu systemu oraz monitoringu na żywo.

## Dostępne dowody

- Istniejący interfejs i zasoby motywów: `server/static/style.css`, `server/static/images/LUMS_Logo.jpg` oraz `server/static/images/lumsstadium.jpg`.
- Istniejące implementacje zarejestrowanych klientów, telemetrii, zadań aktualizacji, RBAC, audytu i kopii zapasowych znajdują się w pakiecie `server/`.
- Nie przedstawiono zweryfikowanych opinii klientów, wskaźników porównawczych produktu ani integracji automatycznego wykrywania infrastruktury.

## Zasady produktu

- Pozostawiać administratorom kontrolę nad zmianami systemowymi.
- Umożliwiać weryfikację stanu operacyjnego i wyników aktualizacji.
- Egzekwować reguły dostępu na serwerze, a nie tylko w interfejsie.
- Rozróżniać fakty zgłaszane przez klientów od inwentarza utrzymywanego ręcznie.
