import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from bs4 import BeautifulSoup

DATA_FILE = Path("grocery_data.json")
BACKUP_DIR = Path("backups")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
TIMEOUT = 20

# Per store kun je hier selectors of regex verbeteren als je later echte pagina’s hebt.
STORE_RULES: Dict[str, Dict[str, Any]] = {
    "ah": {
        "selectors": [
            '[itemprop="price"]',
            'meta[property="product:price:amount"]',
            '[data-testhook="price"]',
            ".price-amount",
        ],
        "regexes": [
            r'"price"\s*:\s*"(\d+[.,]\d{2})"',
            r'€\s?(\d+[.,]\d{2})',
        ],
    },
    "jumbo": {
        "selectors": [
            '[itemprop="price"]',
            'meta[property="product:price:amount"]',
            '[data-testid="price"]',
            ".price",
        ],
        "regexes": [
            r'"price"\s*:\s*"(\d+[.,]\d{2})"',
            r'€\s?(\d+[.,]\d{2})',
        ],
    },
    "lidl": {
        "selectors": [
            '[itemprop="price"]',
            'meta[property="product:price:amount"]',
            ".price",
            ".m-price__price",
        ],
        "regexes": [
            r'"price"\s*:\s*"(\d+[.,]\d{2})"',
            r'€\s?(\d+[.,]\d{2})',
        ],
    },
    "aldi": {
        "selectors": [
            '[itemprop="price"]',
            'meta[property="product:price:amount"]',
            ".price",
        ],
        "regexes": [
            r'"price"\s*:\s*"(\d+[.,]\d{2})"',
            r'€\s?(\d+[.,]\d{2})',
        ],
    },
}


def load_products() -> list[dict]:
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"{DATA_FILE} niet gevonden")
    with DATA_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("grocery_data.json moet een lijst met producten bevatten")
    return data


def save_backup() -> Path:
    BACKUP_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"grocery_data_{ts}.json"
    shutil.copy2(DATA_FILE, backup_path)
    return backup_path


def save_products(products: list[dict]) -> None:
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def clean_price(raw: str) -> Optional[float]:
    if not raw:
        return None

    value = raw.strip()
    value = value.replace("\xa0", " ").replace("EUR", "").replace("€", "").strip()

    # Probeer NL-formaten als 1.234,56 en eenvoudige 12,34 / 12.34
    if "," in value and "." in value:
        # aannemen dat . duizendtallen zijn en , decimalen
        value = value.replace(".", "").replace(",", ".")
    else:
        value = value.replace(",", ".")

    match = re.search(r"(\d+(?:\.\d{1,2})?)", value)
    if not match:
        return None

    try:
        return round(float(match.group(1)), 2)
    except ValueError:
        return None


def extract_price_from_html(html: str, store_id: str) -> Optional[float]:
    rules = STORE_RULES.get(store_id, {})
    soup = BeautifulSoup(html, "html.parser")

    for selector in rules.get("selectors", []):
        el = soup.select_one(selector)
        if not el:
            continue

        # eerst content/value proberen, daarna tekst
        raw = el.get("content") or el.get("value") or el.get_text(" ", strip=True)
        price = clean_price(raw)
        if price is not None:
            return price

    for pattern in rules.get("regexes", []):
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            price = clean_price(match.group(1))
            if price is not None:
                return price

    return None


def fetch_html(url: str) -> str:
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(url, headers=headers, timeout=TIMEOUT)
    response.raise_for_status()
    return response.text


def update_product_prices(product: dict) -> dict:
    source_urls: Dict[str, str] = product.get("sourceUrls", {})
    prices: Dict[str, float] = dict(product.get("prices", {}))
    changed = False
    notes = []

    for store_id, url in source_urls.items():
        if not url:
            continue

        try:
            html = fetch_html(url)
            new_price = extract_price_from_html(html, store_id)

            if new_price is None:
                notes.append(f"{store_id}: prijs niet gevonden")
                continue

            old_price = prices.get(store_id)
            prices[store_id] = new_price

            if old_price != new_price:
                changed = True
                notes.append(f"{store_id}: {old_price} -> {new_price}")
            else:
                notes.append(f"{store_id}: ongewijzigd ({new_price})")

        except Exception as e:
            notes.append(f"{store_id}: fout ({e})")

    if changed:
        product["prices"] = prices
        product["lastUpdated"] = datetime.now(timezone.utc).isoformat()

    product["_updateNotes"] = notes
    return product


def main(dry_run: bool = False) -> None:
    products = load_products()

    updated_products = []
    changed_count = 0

    for product in products:
        updated = update_product_prices(product)
        updated_products.append(updated)

        notes = updated.get("_updateNotes", [])
        if notes:
            print(f"\n{updated.get('name', 'Onbekend product')}")
            for note in notes:
                print(f" - {note}")

        if "lastUpdated" in updated:
            changed_count += 1

    for product in updated_products:
        product.pop("_updateNotes", None)

    if dry_run:
        print(f"\nDRY RUN klaar. {changed_count} product(en) zouden zijn bijgewerkt.")
        return

    backup = save_backup()
    save_products(updated_products)
    print(f"\nKlaar. Backup opgeslagen als: {backup}")
    print(f"{changed_count} product(en) bijgewerkt.")


if __name__ == "__main__":
    # Zet op True als je eerst wilt testen zonder weg te schrijven
    main(dry_run=False)