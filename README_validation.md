# Product validation pipeline

Plaats deze bestanden in de root van je backend:

```text
grocery-backend/
├── main.py
├── products_schema.py
├── validate_products.py
├── data/
│   └── products.json
```

## Installatie

Je hebt `pydantic` al in je FastAPI-project. Zo niet:

```bash
pip install pydantic
```

## Handmatig valideren

Vanuit de backend root:

```bash
python validate_products.py
```

Of met expliciet pad:

```bash
python validate_products.py data/products.json
```

## Output

Er wordt een rapport gemaakt op:

```text
data/products_validation_report.json
```

## Bij succes

Je ziet:

```json
"status": "valid"
```

## Bij fout

Het script stopt met exit-code `1`. Dat is handig voor GitHub Actions / Render / CI.
