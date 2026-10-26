# Pakiet narzędzi aktualizacyjnych do pobrania

Po pomyślnym zakończeniu przepływu pracy `Tests` na gałęzi `main` przepływ
pracy `Updater package` tworzy artefakt `lums-update-tools-<commit>.tar.gz`
oraz sumę kontrolną SHA-256. Pobierz je z sekcji **Artifacts** pomyślnego
uruchomienia tego przepływu pracy; artefakty kompilacji są przechowywane
przez 90 dni.

Po opublikowaniu wydania przepływ pracy uruchamia zestaw testów dla
opublikowanego tagu przed dołączeniem archiwum aktualizatora i
deterministycznego archiwum źródłowego. Archiwum źródłowe zawiera sumę
kontrolną SHA-256 oraz identyfikator przetestowanego commitu; Centrum
aktualizacji wyświetla wydania dopiero wtedy, gdy dostępne są wszystkie trzy
zasoby weryfikacji źródła.

Pakiet narzędzi aktualizacyjnych to wygodny plik do pobrania, a nie pakiet
Debiana. Kontener WWW nie instaluje bezpośrednio archiwum źródłowego. Nie
używaj go do aktualizowania środowiska produkcyjnego, dopóki osobno
zainstalowany aktualizator hosta nie przejdzie kontroli wdrożeniowych i nie
zweryfikuje tworzenia kopii zapasowej bazy danych oraz sposobu wycofania zmian
dla dokładnie tego wdrożenia.

Źródło: [oryginał po angielsku](../../update-tools-package.md).
