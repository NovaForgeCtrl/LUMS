# Szybki start z LUMS — polski

Ten krótki przewodnik jest przeznaczony dla osób, które dopiero poznają LUMS
lub Linux. Przetłumaczone przewodniki dla użytkowników i administratorów
znajdują się w [indeksie dokumentacji według języka](../../README.md).
Angielskie dokumenty źródłowe pozostają technicznym punktem odniesienia;
przed zmianami w systemie produkcyjnym postępuj zgodnie z nimi, jeśli
tłumaczenie jest niepełne lub różni się od źródła.

## Czym jest LUMS?

LUMS centralnie zarządza komputerami z systemem Linux. Serwer pokazuje
klientów, zainstalowane oprogramowanie i dostępne aktualizacje. Agent na każdym
kliencie wykonuje zatwierdzone operacje za pomocą systemowego menedżera
pakietów: APT w Debianie/Ubuntu i pacman w Arch Linux. LUMS nie instaluje
automatycznie wszystkich aktualizacji.

## Jeśli tylko korzystasz z LUMS

Otwórz adres internetowy przekazany przez administratora i zaloguj się na
własne konto. Dostępne działania zależą od Twoich uprawnień. Nie udostępniaj
konta ani tokenu klienta. Język można wybrać w prawym górnym rogu strony
logowania; po zalogowaniu LUMS może zapisać ten wybór na koncie.

## Instalacja i obsługa

Pomyślny test nie oznacza, że serwer produkcyjny jest gotowy. Bezpieczne
wdrożenie wymaga między innymi HTTPS, chronionego sekretu aplikacji, trwałego
przechowywania bazy danych i sprawdzonych kopii zapasowych. Serwer i klienci
Linux są konfigurowani oddzielnie. Postępuj zgodnie z
[angielskim podręcznikiem instalacji](../../../install.md). Przed wykonaniem
polecenia zastąp przykładowe wartości, takie jak `LUMS-SERVER`, i sprawdź
każdą ścieżkę. Jeśli LUMS już działa, użyj instrukcji aktualizacji z
[podręcznika administracji](../../../administration.md), a nie procedury
pierwszej instalacji.

Podczas zwykłej aktualizacji nigdy nie usuwaj woluminu Docker `lums-data` —
zawiera bazę danych. Zachowaj istniejące podłączenia sekretu i kopii zapasowych
oraz ustawienia bezpieczeństwa kontenera. Przykładowe polecenia nie pasują do
każdej instalacji; najpierw porównaj je z działającym kontenerem.

## Pierwsze kontrole w razie problemu

Na serwerze te polecenia pokazują stan kontenera, ostatnie logi aplikacji i
stan Nginx:

```bash
sudo docker ps -a --filter name=lums
sudo docker logs --tail 100 lums
sudo systemctl status nginx --no-pager
sudo nginx -t
```

`sudo` może poprosić o hasło do Linuksa. Te kontrole nie zmieniają
konfiguracji. Nie zaczynaj od usuwania bazy danych lub woluminu Docker,
uruchamiania kontenera z uprawnieniami administratora ani wyłączania
zabezpieczeń. Przed udostępnieniem logów usuń hasła, tokeny, klucze i dane
osobowe.

## Szczegółowa dokumentacja

* [Opis projektu](Opis%20projektu.md)
* [Instalacja i aktualizacje](Instalacja%20i%20aktualizacje.md)
* [Administracja i kopie zapasowe](Administracja%20i%20kopie%20zapasowe.md)
* [Rozwiązywanie problemów](Rozwiązywanie%20problemów.md)
* [Model bezpieczeństwa](Model%20bezpieczeństwa.md)
