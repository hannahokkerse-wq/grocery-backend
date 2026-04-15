Stap 2: automatische JSON updater per winkel

Wat dit doet:
- update_store_prices.py leest data/products.json
- per winkel zoekt het matches in:
  - data/store_sources/ah.json
  - data/store_sources/jumbo.json
  - data/store_sources/lidl.json
  - data/store_sources/aldi.json
- daarna werkt het automatisch prijzen bij
- het maakt ook een rapport:
  - data/last_update_report.json

Belangrijk:
Dit is een stabiele tussenstap.
Je hoeft dus nog niet direct live websites te scrapen.

Workflow:
1. Vul per winkel een JSON bronbestand
2. Run:
   python update_store_prices.py
3. Bekijk:
   data/last_update_report.json

Bestandsstructuur:
grocery-backend/
  update_store_prices.py
  scrapers/
    manual_sources.py
  data/
    products.json
    store_sources/
      ah.json
      jumbo.json
      lidl.json
      aldi.json

Waarom dit handig is:
- veel minder foutgevoelig dan direct scrapen
- je kunt per winkel data importeren
- later kun je per winkel een echte scraper aansluiten
