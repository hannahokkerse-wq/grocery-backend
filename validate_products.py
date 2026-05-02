import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import List, Dict

from products_schema import Product, REQUIRED_STORES


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"JSON parse error in {path}: {exc}")


def base_name(name: str) -> str:
    lowered = name.lower().strip()
    for suffix in [" huismerk", " voordeel"]:
        if lowered.endswith(suffix):
            return lowered[: -len(suffix)].strip()
    return lowered


def validate_dataset(path: Path) -> Dict:
    raw = load_json(path)

    if not isinstance(raw, list):
        raise SystemExit("products.json moet een JSON-array zijn")

    errors: List[str] = []
    products: List[Product] = []

    for index, item in enumerate(raw):
        try:
            products.append(Product.model_validate(item))
        except Exception as exc:
            product_name = item.get("name", f"index {index}") if isinstance(item, dict) else f"index {index}"
            errors.append(f"{product_name}: {exc}")

    ids = [p.id for p in products]
    names = [p.name.strip().lower() for p in products]

    duplicate_ids = [id_ for id_, count in Counter(ids).items() if count > 1]
    duplicate_names = [name for name, count in Counter(names).items() if count > 1]

    if duplicate_ids:
        errors.append(f"Duplicate ids: {duplicate_ids}")

    if duplicate_names:
        errors.append(f"Duplicate names: {duplicate_names}")

    if ids:
        missing_ids = sorted(set(range(1, max(ids) + 1)) - set(ids))
    else:
        missing_ids = []

    if missing_ids:
        errors.append(f"Missing ids: {missing_ids}")

    # Check semantic duplicates: same base product repeated more than 3 times.
    base_groups = defaultdict(list)
    for p in products:
        base_groups[base_name(p.name)].append(p.name)

    suspicious_groups = {
        base: names
        for base, names in base_groups.items()
        if len(names) > 3
    }

    if suspicious_groups:
        errors.append(f"Suspicious duplicate product groups: {suspicious_groups}")

    # Check substitute references.
    product_names = set(p.name for p in products)
    missing_substitutes = [
        {"id": p.id, "name": p.name, "substitute": p.substitute}
        for p in products
        if p.substitute and p.substitute not in product_names
    ]

    if missing_substitutes:
        errors.append(f"Substitutes not found as product names: {missing_substitutes[:10]}")

    category_counts = Counter(p.category for p in products)
    tag_counts = Counter(tag for p in products for tag in p.tags)

    report = {
        "file": str(path),
        "product_count": len(products),
        "min_id": min(ids) if ids else None,
        "max_id": max(ids) if ids else None,
        "duplicate_ids": duplicate_ids,
        "duplicate_names": duplicate_names,
        "missing_ids": missing_ids,
        "required_stores": sorted(REQUIRED_STORES),
        "category_counts": dict(sorted(category_counts.items())),
        "tag_counts": dict(sorted(tag_counts.items())),
        "products_with_substitute": sum(1 for p in products if p.substitute),
        "products_without_substitute": sum(1 for p in products if not p.substitute),
        "errors": errors,
        "status": "valid" if not errors else "invalid",
    }

    return report


def main():
    parser = argparse.ArgumentParser(description="Validate Grocery Discount AI products.json")
    parser.add_argument(
        "path",
        nargs="?",
        default="data/products.json",
        help="Pad naar products.json. Default: data/products.json",
    )
    parser.add_argument(
        "--report",
        default="data/products_validation_report.json",
        help="Pad voor validatierapport. Default: data/products_validation_report.json",
    )
    args = parser.parse_args()

    product_path = Path(args.path)
    report_path = Path(args.report)

    if not product_path.exists():
        raise SystemExit(f"Niet gevonden: {product_path}")

    report = validate_dataset(product_path)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if report["status"] != "valid":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
