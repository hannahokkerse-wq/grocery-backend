import json
import re
from pathlib import Path
from datetime import date
from scrapers.manual_sources import STORE_SOURCE_MAP

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "products.json"
REPORT_PATH = BASE_DIR / "data" / "last_update_report.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def normalize_text(value: str) -> str:
    value = value.lower().strip()
    value = value.replace("½", "half")
    value = value.replace("1l", "1 l")
    value = value.replace("500g", "500 g")
    value = value.replace("400g", "400 g")
    value = value.replace("2kg", "2 kg")
    value = value.replace("1kg", "1 kg")
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def score_match(product_name: str, source_name: str) -> int:
    p = normalize_text(product_name)
    s = normalize_text(source_name)

    if p == s:
        return 100

    p_words = set(p.split())
    s_words = set(s.split())
    overlap = len(p_words & s_words)

    if overlap == 0:
        return 0

    return overlap * 10


def find_best_match(product_name: str, source_items: list[dict], min_score: int = 20):
    best_item = None
    best_score = -1

    for item in source_items:
        source_name = item.get("name", "")
        score = score_match(product_name, source_name)
        if score > best_score:
            best_score = score
            best_item = item

    if best_score < min_score:
        return None, best_score

    return best_item, best_score


def recalculate_value_scores(products: list[dict]) -> list[dict]:
    for product in products:
        prices = list(product.get("prices", {}).values())
        prices = [float(p) for p in prices if p is not None]
        if not prices:
            continue

        lowest = min(prices)
        highest = max(prices)
        quality = float(product.get("qualityScore", 7.0))

        if highest <= 0:
            product["valueScore"] = round(quality, 1)
            continue

        price_component = max(0.0, 10 - ((lowest / highest) * 5))
        value_score = min(10.0, max(1.0, quality + (10 - price_component) - 2))
        product["valueScore"] = round(value_score, 1)

    return products


def update_store(products: list[dict], store_id: str, source_items: list[dict]):
    updated = 0
    unchanged = 0
    missing = 0
    report_rows = []

    for product in products:
        if store_id not in product.get("prices", {}):
            continue

        match, score = find_best_match(product["name"], source_items)
        old_price = product["prices"].get(store_id)

        if not match:
            missing += 1
            report_rows.append({
                "product": product["name"],
                "store": store_id,
                "status": "not_found",
                "oldPrice": old_price,
                "newPrice": None,
                "matchScore": score,
            })
            continue

        new_price = match.get("price")
        if new_price is None:
            missing += 1
            report_rows.append({
                "product": product["name"],
                "store": store_id,
                "status": "no_price",
                "oldPrice": old_price,
                "newPrice": None,
                "matchScore": score,
                "matchedName": match.get("name"),
            })
            continue

        if float(old_price) != float(new_price):
            product["prices"][store_id] = float(new_price)
            product["lastUpdated"] = str(date.today())
            updated += 1
            status = "updated"
        else:
            unchanged += 1
            status = "unchanged"

        report_rows.append({
            "product": product["name"],
            "store": store_id,
            "status": status,
            "oldPrice": old_price,
            "newPrice": float(new_price),
            "matchScore": score,
            "matchedName": match.get("name"),
        })

    return products, {
        "store": store_id,
        "updated": updated,
        "unchanged": unchanged,
        "missing": missing,
        "rows": report_rows,
    }


def main():
    products = load_json(DATA_PATH)
    report = {
        "updatedAt": str(date.today()),
        "stores": [],
    }

    for store_id, loader in STORE_SOURCE_MAP.items():
        source_items = loader()
        products, store_report = update_store(products, store_id, source_items)
        report["stores"].append(store_report)
        print(f"{store_id}: {store_report['updated']} updated, {store_report['unchanged']} unchanged, {store_report['missing']} missing")

    products = recalculate_value_scores(products)
    save_json(DATA_PATH, products)
    save_json(REPORT_PATH, report)

    total_updated = sum(s["updated"] for s in report["stores"])
    print(f"Klaar. {total_updated} prijzen aangepast.")
    print(f"Rapport opgeslagen in: {REPORT_PATH}")


if __name__ == "__main__":
    main()
