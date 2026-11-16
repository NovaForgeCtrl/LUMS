# Topologia infrastruktury LUMS

## Cel

Uwierzytelniona strona `/infrastructure` łączy zarejestrowanych klientów LUMS
i ręcznie utrzymywane elementy infrastruktury w jednym widoku zależności. To
inwentaryzacja i mapa relacji, a nie system automatycznego wykrywania sieci
ani zarządzania konfiguracją.

## Źródła danych i odpowiedzialność

- Zarejestrowani klienci LUMS są pobierani z istniejącego rejestru klientów i
  pojawiają się automatycznie wraz ze zgłoszoną nazwą hosta, adresem IP,
  systemem operacyjnym oraz stanem włączenia/raportowania. Wyłączeni klienci
  pozostają widoczni, aby zachować czytelność istniejących relacji. Na stronie
  topologii te wpisy są tylko do odczytu; zarządzaj klientem w standardowym
  procesie zarządzania klientami.
- Serwery, maszyny wirtualne, kontenery, urządzenia sieciowe, usługi i zasoby
  pamięci masowej można dodać ręcznie, podając nazwę hosta, adres IP, rolę,
  lokalizację i notatki.
- Relacje są utrzymywane ręcznie. Obsługiwane typy to `depends on`, `hosts`,
  `connects to` i `runs on`.
- Strona nie skanuje podsieci, nie odpytuje API chmurowych ani nie wnioskuje o
  zależnościach na podstawie konfiguracji usług lub kontenerów. Aktualizuj
  ręcznie wprowadzoną inwentaryzację i relacje.

## Kontrola dostępu i audyt

Użytkownicy z uprawnieniem `clients.view` mogą przeglądać topologię. Tworzenie,
edycja i usuwanie ręcznych wpisów lub relacji wymaga uprawnień administratora
oraz uprawnienia `infrastructure.manage`. Aplikacja wymaga standardowej
uwierzytelnionej sesji, ochrony CSRF i rejestrowania zmian w dzienniku audytu.

Uprawnienie `infrastructure.manage` zależy od `users.manage` i
`clients.view`; administratorom jest nadawane przez migrację bazy danych
`016-infrastructure-topology`. Usunięcie ręcznie zarządzanego węzła usuwa
również jego rekordy relacji. Usunięcie klienta usuwa relacje odwołujące się
do tego klienta.

## Odczytywanie mapy

Mapa rozmieszcza węzły według kategorii i rysuje każdą zapisaną relację jako
krawędź ze wskazanym kierunkiem. **Współdzielona zależność** to węzeł, do
którego co najmniej dwa inne węzły prowadzą relacją `depends on`. To przydatny
sygnał do sprawdzenia potencjalnego centralnego punktu awarii, a nie pełna
analiza dostępności lub skutków awarii. Mapa nie uwzględnia nadmiarowości,
przełączania awaryjnego, pojemności, segmentacji sieci ani nieodnotowanych
zależności.

Aby sprawdzić dokładną nazwę hosta, adres IP, rolę, lokalizację i szczegóły
relacji, użyj tabel inwentaryzacji i relacji. Topologia korzysta z aktualnie
wybranego motywu LUMS i współpracuje ze wspólnym, zwijanym paskiem bocznym.

Źródło: [oryginał po angielsku](../../../LUMS_Infrastructure_Topology.md).
