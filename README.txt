Optie C complete files

Inhoud:
- main.py
- update_prices.py
- data/products.json
- data/price_updates.example.json

Wat dit doet:
- backend leest producten uit data/products.json
- update_prices.py werkt prijzen bij vanuit:
  - data/price_updates.json
  - data/price_updates.csv
- als er geen updates zijn, blijft bestaande data gewoon staan

Aanbevolen gebruik:
1. Zet main.py in je backend root
2. Maak map data/
3. Zet products.json in data/products.json
4. Zet update_prices.py in backend root
5. Optioneel: maak data/price_updates.json op basis van price_updates.example.json

Run handmatig:
python update_prices.py
of:
python update_prices.py --source json
python update_prices.py --source csv
