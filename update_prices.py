import json
from pathlib import Path
from datetime import date
import csv
import argparse

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "products.json"
UPDATES_JSON_PATH = BASE_DIR / "data" / "price_updates.json"
UPDATES_CSV_PATH = BASE_DIR / "data" / "price_updates.csv"


def load_products():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_products(products):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def apply_json_updates(products, updates_path):
    if not updates_path.exists():
        print(f"Geen JSON updates gevonden op: {updates_path}")
        return products, 0

    with open(updates_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    updates = payload.get("updates", [])
    applied = 0

    for update in updates:
        name = update.get("name")
        store = update.get("store")
        price = update.get("price")

        if not name or not store or price is None:
            continue

        for product in products:
            if product["name"].strip().lower() == name.strip().lower():
                if "prices" in product and store in product["prices"]:
                    old_price = product["prices"][store]
                    product["prices"][store] = float(price)
                    product["lastUpdated"] = str(date.today())
                    applied += 1
                    print(f"[JSON] {name} | {store}: {old_price} -> {price}")
                break

    return products, applied


def apply_csv_updates(products, updates_path):
    if not updates_path.exists():
        print(f"Geen CSV updates gevonden op: {updates_path}")
        return products, 0

    applied = 0
    with open(updates_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("name")
            store = row.get("store")
            price = row.get("price")

            if not name or not store or price in [None, ""]:
                continue

            for product in products:
                if product["name"].strip().lower() == name.strip().lower():
                    if "prices" in product and store in product["prices"]:
                        old_price = product["prices"][store]
                        product["prices"][store] = float(price)
                        product["lastUpdated"] = str(date.today())
                        applied += 1
                        print(f"[CSV] {name} | {store}: {old_price} -> {price}")
                    break

    return products, applied


def recalculate_value_scores(products):
    for product in products:
        prices = list(product.get("prices", {}).values())
        if not prices:
            continue
        lowest = min(prices)
        highest = max(prices)
        quality = float(product.get("qualityScore", 7.0))

        if highest == 0:
            value_score = quality
        else:
            price_factor = 10 - ((lowest / highest) * 5)
            value_score = round(min(10, max(1, quality + (10 - price_factor) - 2)), 1)

        product["valueScore"] = value_score

    return products


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["json", "csv", "both"], default="both")
    args = parser.parse_args()

    products = load_products()
    total_applied = 0

    if args.source in ["json", "both"]:
        products, applied = apply_json_updates(products, UPDATES_JSON_PATH)
        total_applied += applied

    if args.source in ["csv", "both"]:
        products, applied = apply_csv_updates(products, UPDATES_CSV_PATH)
        total_applied += applied

    products = recalculate_value_scores(products)
    save_products(products)

    print(f"Klaar. {total_applied} prijsupdates toegepast.")
    print(f"Data opgeslagen in: {DATA_PATH}")


if __name__ == "__main__":
    main()
