# PRANA Scent — Google Merchant Center feed

Automatyczny feed XML produktów PRANA Scent dla Google Merchant Center, bez instalowania aplikacji Google & YouTube w Shopify.

## Zasada działania
- Generator `generate_feed.py` odczytuje publiczne dane produktów Shopify przez Ajax Product API.
- Feed obejmuje 7 zapachów świec i wszystkie dostępne warianty, bez karty podarunkowej.
- Dla każdego wariantu zapisuje identyfikator, grupę, cenę w PLN, dostępność, zdjęcie, link, rozmiar i kolor.
- GitHub Actions uruchamia generator codziennie o 03:17 UTC i publikuje `merchant-feed.xml` przez GitHub Pages.
- Nie wymaga tokenu administracyjnego Shopify.

## Uruchomienie
1. GitHub repo → **Settings → Pages → Build and deployment → Source = GitHub Actions**.
2. **Actions → PRANA Merchant feed → Run workflow**.
3. Sprawdź, czy workflow zakończył się sukcesem i czy plik XML jest dostępny pod publicznym adresem GitHub Pages.
4. Dopiero wtedy dodaj zweryfikowany adres pliku jako źródło w Google Merchant Center.
5. Sprawdź ceny, zdjęcia, dostępność i komunikaty diagnostyczne Merchant Center.

## Ograniczenia
- Publiczny endpoint Shopify musi być dostępny; błędy pobierania blokują generowanie nowego feedu.
- Lista uchwytów 7 produktów znajduje się w `HANDLES` w skrypcie; nowe zapachy wymagają dopisania uchwytu.
- Dodatkowe warianty już obsługiwanego zapachu są uwzględniane automatycznie.
- Ceny i stany są odczytywane przy każdym uruchomieniu, a nie zapisywane na stałe w kodzie.
- Wariant bez własnego zdjęcia korzysta ze zdjęcia produktu; przed uruchomieniem kampanii trzeba sprawdzić trafność zdjęć.
- Aktualizacje GitHub Actions mogą się opóźniać, więc należy monitorować działanie workflow.

## Test
```bash
python3 generate_feed.py --output merchant-feed.xml
```

**Stan:** repozytorium zawiera generator, ale publikacja i pobieranie z produkcyjnego Shopify wymagają pierwszego udanego workflow. Nie uruchamiaj kampanii produktowych przed sprawdzeniem feedu i statusów produktów.
