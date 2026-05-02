from fastapi import FastAPI, HTTPException
import os
import json
import re
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from products_schema import Product
from sqlmodel import SQLModel, Field, Session, create_engine, select
from contextlib import asynccontextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./grocery_discount.db")
engine = create_engine(DATABASE_URL, echo=False)

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "products.json"
FALLBACK_DATA_PATH = BASE_DIR / "data" / "products_fallback.json"
PRODUCTS_CACHE: List[Dict] = []
PRODUCTS_SOURCE = "not-loaded"
PRODUCTS_VALIDATION_WARNING: Optional[str] = None


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str


class ShoppingList(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int
    name: str
    product_ids: str


class PriceAlert(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int
    product_id: int
    target_price: float


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not DATA_PATH.exists():
        raise RuntimeError(f"products.json not found at {DATA_PATH}")

    global PRODUCTS_CACHE
    PRODUCTS_CACHE = load_validated_products_with_fallback()

    yield


app = FastAPI(title="Grocery Discount API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

STORES = [
    {"id": "ah", "name": "Albert Heijn", "distanceKm": 1.2},
    {"id": "jumbo", "name": "Jumbo", "distanceKm": 2.1},
    {"id": "lidl", "name": "Lidl", "distanceKm": 3.0},
    {"id": "aldi", "name": "Aldi", "distanceKm": 3.5},
    {"id": "plus", "name": "Plus", "distanceKm": 2.6},
    {"id": "dirk", "name": "Dirk", "distanceKm": 2.8},
]

STORE_NAME_MAP = {store["id"]: store["name"] for store in STORES}
CHAT_MEMORY: Dict[str, List[Dict[str, str]]] = {}
SESSION_CONTEXT: Dict[str, Dict] = {}


def load_products() -> List[Dict]:
    """
    Producten laden.

    Als PRODUCTS_CACHE gevuld is, gebruikt de API die cache.
    Daardoor kan de backend veilig terugvallen op products_fallback.json
    wanneer data/products.json ongeldig is.
    """
    if PRODUCTS_CACHE:
        return PRODUCTS_CACHE

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_products(products: List[Dict]) -> None:
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def validate_products_data(products: List[Dict]) -> None:
    """
    Valideert products.json bij startup.
    Als data ongeldig is, stopt de backend met een duidelijke foutmelding.
    """
    if not isinstance(products, list):
        raise RuntimeError("products.json moet een JSON-array zijn")

    seen_ids = set()
    seen_names = set()
    errors = []

    for index, product in enumerate(products):
        try:
            validated = Product.model_validate(product)
        except Exception as exc:
            name = product.get("name", f"index {index}") if isinstance(product, dict) else f"index {index}"
            errors.append(f"{name}: {exc}")
            continue

        if validated.id in seen_ids:
            errors.append(f"Duplicate product id: {validated.id}")
        seen_ids.add(validated.id)

        normalized_name = validated.name.strip().lower()
        if normalized_name in seen_names:
            errors.append(f"Duplicate product name: {validated.name}")
        seen_names.add(normalized_name)

    if seen_ids:
        missing_ids = sorted(set(range(1, max(seen_ids) + 1)) - seen_ids)
        if missing_ids:
            errors.append(f"Missing product ids: {missing_ids}")

    if errors:
        preview = "\n".join(errors[:20])
        extra = f"\n... plus {len(errors) - 20} extra fouten" if len(errors) > 20 else ""
        raise RuntimeError(f"products.json validation failed:\n{preview}{extra}")


def load_validated_products_with_fallback() -> List[Dict]:
    """
    Probeert eerst data/products.json.
    Als die ongeldig is, probeert hij data/products_fallback.json.

    Als fallback wordt gebruikt:
    - app start alsnog
    - /health/data laat warning zien
    - API blijft werken met laatst bekende goede dataset
    """
    global PRODUCTS_SOURCE, PRODUCTS_VALIDATION_WARNING

    try:
        products = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        validate_products_data(products)
        PRODUCTS_SOURCE = str(DATA_PATH)
        PRODUCTS_VALIDATION_WARNING = None
        return products
    except Exception as primary_error:
        PRODUCTS_VALIDATION_WARNING = f"Primary products.json invalid: {primary_error}"

        if FALLBACK_DATA_PATH.exists():
            try:
                fallback_products = json.loads(FALLBACK_DATA_PATH.read_text(encoding="utf-8"))
                validate_products_data(fallback_products)
                PRODUCTS_SOURCE = str(FALLBACK_DATA_PATH)
                PRODUCTS_VALIDATION_WARNING += f" | Using fallback: {FALLBACK_DATA_PATH}"
                return fallback_products
            except Exception as fallback_error:
                raise RuntimeError(
                    "products.json én products_fallback.json zijn ongeldig. "
                    f"Primary error: {primary_error}. Fallback error: {fallback_error}"
                )

        raise RuntimeError(
            "products.json is ongeldig en er is geen geldige fallback beschikbaar. "
            f"Zet een geldige fallback op: {FALLBACK_DATA_PATH}. "
            f"Originele fout: {primary_error}"
        )


def valid_prices(product: Dict) -> Dict[str, float]:
    prices = product.get("prices", {})
    return {
        store_id: float(price)
        for store_id, price in prices.items()
        if price is not None and store_id in STORE_NAME_MAP
    }


def get_cheapest_store(product: Dict):
    prices = valid_prices(product)
    if not prices:
        return {"storeId": "", "price": 0.0, "storeName": ""}
    cheapest_store_id = min(prices, key=prices.get)
    return {
        "storeId": cheapest_store_id,
        "price": prices[cheapest_store_id],
        "storeName": STORE_NAME_MAP.get(cheapest_store_id, cheapest_store_id),
    }


def get_best_quality_option(product: Dict):
    cheapest = get_cheapest_store(product)
    return {
        "storeId": cheapest["storeId"],
        "storeName": cheapest["storeName"],
        "qualityScore": product.get("qualityScore", 0),
    }


def get_best_value_option(product: Dict):
    cheapest = get_cheapest_store(product)
    return {
        "storeId": cheapest["storeId"],
        "storeName": cheapest["storeName"],
        "valueScore": product.get("valueScore", 0),
    }


def enrich_product(product: Dict):
    return {
        **product,
        "cheapestOption": get_cheapest_store(product),
        "bestQualityOption": get_best_quality_option(product),
        "bestValueOption": get_best_value_option(product),
    }


def build_basket(items: List[Dict]):
    per_store_totals = []

    for store in STORES:
        store_id = store["id"]
        total = 0.0
        possible = True

        for item in items:
            prices = valid_prices(item)
            if store_id not in prices:
                possible = False
                break
            total += prices[store_id]

        if possible:
            per_store_totals.append({**store, "total": round(total, 2)})

    single_store_best = min(per_store_totals, key=lambda x: x["total"]) if per_store_totals else None

    split_plan = []
    for item in items:
        cheapest = get_cheapest_store(item)
        split_plan.append(
            {
                "item": item["name"],
                "storeId": cheapest["storeId"],
                "storeName": cheapest["storeName"],
                "price": cheapest["price"],
                "substitute": item.get("substitute", ""),
                "qualityScore": item.get("qualityScore"),
                "valueScore": item.get("valueScore"),
            }
        )

    split_total = round(sum(row["price"] for row in split_plan), 2) if split_plan else 0
    savings = round(single_store_best["total"] - split_total, 2) if single_store_best else 0
    avg_quality = round(sum(item.get("qualityScore", 0) for item in items) / len(items), 1) if items else 0
    avg_value = round(sum(item.get("valueScore", 0) for item in items) / len(items), 1) if items else 0

    return {
        "perStoreTotals": per_store_totals,
        "singleStoreBest": single_store_best,
        "splitPlan": split_plan,
        "splitTotal": split_total,
        "savingsVsSingleStore": savings,
        "averageQualityScore": avg_quality,
        "averageValueScore": avg_value,
    }


def ai_deal_insights(items: List[Dict]):
    if not items:
        return [
            "Voeg producten toe en de assistent laat zien wat goedkoop én slim is.",
            "Deze versie vergelijkt prijs, kwaliteit en prijs-kwaliteit.",
        ]

    basket = build_basket(items)
    best_quality_item = max(items, key=lambda i: i.get("qualityScore", 0))
    best_value_item = max(items, key=lambda i: i.get("valueScore", 0))
    weakest_item = min(items, key=lambda i: i.get("qualityScore", 0))

    insights = [
        f"Goedkoopste totaaloptie: €{basket['splitTotal']:.2f}.",
        f"Gemiddelde kwaliteit van je mandje: {basket['averageQualityScore']}/10.",
        f"Gemiddelde prijs-kwaliteit van je mandje: {basket['averageValueScore']}/10.",
        f"Beste kwaliteit in je mandje: {best_quality_item['name']} ({best_quality_item.get('qualityScore', 0)}/10).",
        f"Beste prijs-kwaliteit: {best_value_item['name']} ({best_value_item.get('valueScore', 0)}/10).",
        f"Laagste kwaliteitsscore: {weakest_item['name']} ({weakest_item.get('qualityScore', 0)}/10).",
    ]

    if basket["savingsVsSingleStore"] > 0:
        insights.append(f"Door slim te splitsen tussen winkels bespaar je €{basket['savingsVsSingleStore']:.2f}.")

    return insights


def available_stores_for_product(product: Dict) -> List[str]:
    prices = valid_prices(product)
    return [STORE_NAME_MAP[store_id] for store_id in prices if store_id in STORE_NAME_MAP]


def make_store_answer(products: List[Dict]) -> str:
    if not products:
        return "Ik heb geen producten om winkelinformatie over te geven."

    lines = []
    for product in products[:6]:
        stores = available_stores_for_product(product)
        cheapest = get_cheapest_store(product)
        lines.append(
            f"{product['name']}: beschikbaar bij {', '.join(stores)}. "
            f"De goedkoopste winkel is {cheapest['storeName']} voor €{cheapest['price']:.2f}."
        )
    return " ".join(lines)


def get_visible_scope_summary(
    visible_items: List[Dict],
    active_store: str,
    active_category: str,
    sort_mode: str,
    search_query: str,
) -> str:
    parts = []

    if active_store and active_store != "all":
        parts.append(f"winkel: {STORE_NAME_MAP.get(active_store, active_store)}")

    if active_category and active_category != "Alle":
        parts.append(f"categorie: {active_category}")

    if sort_mode:
        sort_map = {
            "price-asc": "goedkoopste eerst",
            "price-desc": "duurste eerst",
            "name-asc": "naam A-Z",
            "favorites": "favorieten eerst",
            "quality-desc": "beste kwaliteit",
            "value-desc": "beste prijs-kwaliteit",
        }
        parts.append(f"sortering: {sort_map.get(sort_mode, sort_mode)}")

    if search_query:
        parts.append(f"zoekterm: '{search_query}'")

    if visible_items:
        parts.append(f"{len(visible_items)} producten")

    return ", ".join(parts) or "alle producten"


# =========================
# AI V2 HELPER FUNCTIONS
# =========================

def extract_budget(message: str) -> Optional[float]:
    msg = message.lower().replace(",", ".")
    patterns = [
        r"€\s*(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)\s*euro",
        r"onder\s*€?\s*(\d+(?:\.\d+)?)",
        r"max\s*€?\s*(\d+(?:\.\d+)?)",
        r"budget\s*(?:van)?\s*€?\s*(\d+(?:\.\d+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, msg)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
    return None


def contains_any(message: str, words: List[str]) -> bool:
    msg = message.lower()
    return any(word in msg for word in words)


def detect_store(message: str) -> Optional[str]:
    msg = message.lower()
    mapping = {
        "albert heijn": "ah",
        "ah": "ah",
        "jumbo": "jumbo",
        "lidl": "lidl",
        "aldi": "aldi",
        "plus": "plus",
        "dirk": "dirk",
    }
    for label, store_id in mapping.items():
        if label in msg:
            return store_id
    return None


def product_price(product: Dict, preferred_store: Optional[str] = None) -> float:
    prices = valid_prices(product)
    if preferred_store and preferred_store in prices:
        return float(prices[preferred_store])
    if not prices:
        return 0.0
    return float(min(prices.values()))


def product_store_name(product: Dict, preferred_store: Optional[str] = None) -> str:
    if preferred_store:
        return STORE_NAME_MAP.get(preferred_store, preferred_store)
    cheapest = get_cheapest_store(product)
    return cheapest.get("storeName", cheapest.get("storeId", ""))


def total_price(products: List[Dict], preferred_store: Optional[str] = None) -> float:
    return round(sum(product_price(p, preferred_store) for p in products), 2)


def rank_by_value(products: List[Dict], preferred_store: Optional[str] = None) -> List[Dict]:
    def score(product: Dict) -> float:
        price = max(product_price(product, preferred_store), 0.5)
        quality = float(product.get("qualityScore", 0))
        value = float(product.get("valueScore", 0))
        promo_bonus = 0.6 if any(t.lower() in ["bonus", "actie"] for t in product.get("tags", [])) else 0
        return ((value * 1.7) + quality + promo_bonus) / price

    return sorted(products, key=score, reverse=True)


def rank_healthy(products: List[Dict]) -> List[Dict]:
    healthy_categories = {"Groente & Fruit", "Zuivel", "Vis", "Ontbijt", "Sportvoeding"}
    healthy_tags = {"gezond", "vers"}

    def score(product: Dict) -> float:
        tags = set(t.lower() for t in product.get("tags", []))
        category_bonus = 1.4 if product.get("category") in healthy_categories else 0
        tag_bonus = 1.0 if healthy_tags.intersection(tags) else 0
        quality = float(product.get("qualityScore", 0))
        value = float(product.get("valueScore", 0))
        return quality * 1.5 + value * 0.7 + category_bonus + tag_bonus

    return sorted(products, key=score, reverse=True)


def filter_by_categories(products: List[Dict], categories: List[str]) -> List[Dict]:
    wanted = set(categories)
    return [p for p in products if p.get("category") in wanted]


def filter_by_keywords(products: List[Dict], keywords: List[str]) -> List[Dict]:
    keywords = [k.lower() for k in keywords]
    result = []

    for product in products:
        haystack = " ".join(
            [
                product.get("name", ""),
                product.get("category", ""),
                product.get("brandType", ""),
                product.get("reviewLabel", ""),
                " ".join(product.get("tags", [])),
            ]
        ).lower()

        if any(keyword in haystack for keyword in keywords):
            result.append(product)

    return result


def meal_scope_products(message: str, products: List[Dict]) -> Optional[List[Dict]]:
    if contains_any(message, ["ontbijt", "breakfast"]):
        return filter_by_categories(products, ["Ontbijt", "Zuivel", "Brood", "Groente & Fruit"])

    if contains_any(message, ["lunch"]):
        return filter_by_categories(products, ["Brood", "Zuivel", "Groente & Fruit", "Houdbaar", "Vis"])

    if contains_any(message, ["avondeten", "diner", "dinner", "maaltijd", "mealprep", "meal prep"]):
        return filter_by_categories(products, ["Vlees", "Vis", "Groente & Fruit", "Houdbaar", "Diepvries"])

    if contains_any(message, ["snack", "snacks"]):
        return filter_by_categories(products, ["Snacks", "Groente & Fruit", "Zuivel"])

    return None


def choose_under_budget(
    products: List[Dict],
    budget: float,
    preferred_store: Optional[str] = None,
    max_items: int = 8,
) -> List[Dict]:
    chosen = []
    total = 0.0

    for product in rank_by_value(products, preferred_store):
        price = product_price(product, preferred_store)
        if price <= 0:
            continue
        if total + price <= budget:
            chosen.append(product)
            total += price
        if len(chosen) >= max_items:
            break

    return chosen


def format_product_lines(
    products: List[Dict],
    preferred_store: Optional[str] = None,
    max_items: int = 6,
) -> str:
    lines = []

    for product in products[:max_items]:
        price = product_price(product, preferred_store)
        store_name = product_store_name(product, preferred_store)
        lines.append(
            f"- {product['name']} — €{price:.2f} bij {store_name}, "
            f"kwaliteit {product.get('qualityScore', 0)}/10, waarde {product.get('valueScore', 0)}/10"
        )

    return "\n".join(lines)


def explain_scope(
    visible_items: List[Dict],
    items: List[Dict],
    visible_summary: str,
) -> str:
    if items:
        return "Binnen je geselecteerde mandje"
    if visible_items:
        return f"Binnen de huidige filterselectie ({visible_summary})"
    return "Binnen alle producten"


def smart_chat_reply(
    message: str,
    items: List[Dict],
    all_products: List[Dict],
    basket: Optional[Dict] = None,
    session_context: Optional[Dict] = None,
    visible_items: Optional[List[Dict]] = None,
    active_store: Optional[str] = "all",
    active_category: Optional[str] = "Alle",
    sort_mode: Optional[str] = "price-asc",
    search_query: Optional[str] = "",
):
    msg = message.lower().strip()
    visible_items = visible_items or []
    remembered_products = session_context.get("last_products", []) if session_context else []

    reference_words = [
        "deze producten",
        "die producten",
        "deze keuzes",
        "die keuzes",
        "deze lijst",
        "wat ik nu zie",
        "wat nu zichtbaar is",
    ]
    use_remembered = any(term in msg for term in reference_words)

    if use_remembered and remembered_products:
        base_scope = remembered_products
    elif items:
        base_scope = items
    elif visible_items:
        base_scope = visible_items
    else:
        base_scope = all_products

    if not base_scope:
        return "Ik heb op dit moment geen producten om te analyseren.", []

    budget = extract_budget(message)
    preferred_store = detect_store(message)
    if not preferred_store and active_store and active_store != "all":
        preferred_store = active_store

    meal_products = meal_scope_products(message, base_scope)
    scope_items = meal_products if meal_products else base_scope

    if not scope_items:
        return "Ik heb geen passende producten gevonden binnen deze selectie.", []

    visible_summary = get_visible_scope_summary(
        visible_items=visible_items,
        active_store=active_store,
        active_category=active_category,
        sort_mode=sort_mode,
        search_query=search_query or "",
    )
    scope_label = explain_scope(visible_items, items, visible_summary)

    if budget is not None or contains_any(msg, ["budget", "onder", "max", "lijst", "boodschappenlijst", "weekboodschappen"]):
        spend_budget = budget or 25.0
        max_items = 12 if contains_any(msg, ["week", "weekboodschappen"]) else 7
        chosen = choose_under_budget(scope_items, spend_budget, preferred_store, max_items=max_items)

        if not chosen:
            return f"Ik kan binnen €{spend_budget:.2f} geen goede combinatie vinden in deze selectie.", []

        total = total_price(chosen, preferred_store)
        store_text = f" bij {STORE_NAME_MAP.get(preferred_store, preferred_store)}" if preferred_store else " op basis van de goedkoopste winkel per product"

        return (
            f"{scope_label} stel ik dit budgetmandje voor{store_text}. "
            f"Totaal: €{total:.2f} van maximaal €{spend_budget:.2f}.\n"
            f"{format_product_lines(chosen, preferred_store, max_items=max_items)}",
            chosen[:4],
        )

    if contains_any(msg, ["gezond", "gezonde", "gezondste", "fit"]):
        healthy = rank_healthy(scope_items)
        return (
            f"{scope_label} zijn dit de gezondste keuzes:\n"
            f"{format_product_lines(healthy, preferred_store, max_items=6)}",
            healthy[:4],
        )

    if contains_any(msg, ["eiwit", "eiwitrijk", "proteïne", "protein", "spiermassa", "sport"]):
        protein = filter_by_keywords(scope_items, ["kwark", "kip", "zalm", "tonijn", "ei", "eieren", "proteïne", "rundergehakt", "vis"])
        if not protein:
            protein = filter_by_categories(scope_items, ["Zuivel", "Vlees", "Vis", "Sportvoeding"])
        protein = rank_by_value(protein, preferred_store)

        if not protein:
            return "Ik vind binnen deze selectie geen duidelijke eiwitrijke producten.", []

        return (
            f"{scope_label} zijn dit sterke eiwitrijke keuzes:\n"
            f"{format_product_lines(protein, preferred_store, max_items=6)}",
            protein[:4],
        )

    if meal_products:
        meal_name = "maaltijd"
        if "ontbijt" in msg:
            meal_name = "ontbijt"
        elif "lunch" in msg:
            meal_name = "lunch"
        elif contains_any(msg, ["avondeten", "diner", "dinner"]):
            meal_name = "avondeten"
        elif contains_any(msg, ["mealprep", "meal prep"]):
            meal_name = "mealprep"

        best_meal = rank_by_value(scope_items, preferred_store)[:6]
        total = total_price(best_meal, preferred_store)

        return (
            f"{scope_label} is dit een slimme {meal_name}-selectie. "
            f"Totaal ongeveer: €{total:.2f}.\n"
            f"{format_product_lines(best_meal, preferred_store, max_items=6)}",
            best_meal[:4],
        )

    if contains_any(msg, ["winkel", "winkels", "supermarkt", "supermarkten", "beschikbaar"]):
        if preferred_store:
            store_products = rank_by_value(scope_items, preferred_store)[:6]
            return (
                f"{scope_label} zijn dit de beste keuzes bij {STORE_NAME_MAP.get(preferred_store, preferred_store)}:\n"
                f"{format_product_lines(store_products, preferred_store, max_items=6)}",
                store_products[:4],
            )

        return make_store_answer(scope_items[:6]), scope_items[:4]

    if contains_any(msg, ["aanbieding", "bonus", "actie"]):
        promo_items = [
            item for item in scope_items
            if any(tag.lower() in ["bonus", "actie"] for tag in item.get("tags", []))
        ]
        promo_items = rank_by_value(promo_items, preferred_store)

        if promo_items:
            return (
                f"{scope_label} zijn dit de beste aanbiedingen/acties:\n"
                f"{format_product_lines(promo_items, preferred_store, max_items=6)}",
                promo_items[:4],
            )

        return "Ik zie binnen deze selectie geen duidelijke aanbiedingen of acties.", []

    if contains_any(msg, ["goedkoop", "goedkope", "besparen", "goedkoopst", "laagste prijs"]):
        cheapest_sorted = sorted(scope_items, key=lambda i: product_price(i, preferred_store))
        return (
            f"{scope_label} zijn dit de goedkoopste producten:\n"
            f"{format_product_lines(cheapest_sorted, preferred_store, max_items=6)}",
            cheapest_sorted[:4],
        )

    if contains_any(msg, ["prijs-kwaliteit", "waarde", "beste keuze", "beste deal"]):
        best_value = rank_by_value(scope_items, preferred_store)
        return (
            f"{scope_label} zijn dit de beste prijs-kwaliteit keuzes:\n"
            f"{format_product_lines(best_value, preferred_store, max_items=6)}",
            best_value[:4],
        )

    if contains_any(msg, ["kwaliteit", "beste kwaliteit", "hoogste kwaliteit"]):
        best_quality = sorted(scope_items, key=lambda i: i.get("qualityScore", 0), reverse=True)
        return (
            f"{scope_label} zijn dit de producten met de hoogste kwaliteit:\n"
            f"{format_product_lines(best_quality, preferred_store, max_items=6)}",
            best_quality[:4],
        )

    if contains_any(msg, ["mandje", "basket", "totaal"]):
        if items:
            scope_basket = basket or build_basket(items)
            return (
                f"Je geselecteerde mandje heeft een goedkoopste totaalprijs van €{scope_basket['splitTotal']:.2f}. "
                f"Gemiddelde kwaliteit: {scope_basket['averageQualityScore']}/10. "
                f"Gemiddelde prijs-kwaliteit: {scope_basket['averageValueScore']}/10.",
                items[:4],
            )

        ranked = rank_by_value(scope_items, preferred_store)[:6]
        return (
            f"Je hebt nog geen mandje geselecteerd. Als startadvies raad ik deze producten aan:\n"
            f"{format_product_lines(ranked, preferred_store, max_items=6)}",
            ranked[:4],
        )

    if contains_any(msg, ["wat zie ik", "wat staat er", "wat is zichtbaar"]):
        ranked = rank_by_value(scope_items, preferred_store)
        return (
            f"{scope_label} vallen {len(scope_items)} producten binnen de analyse. "
            f"De beste prijs-kwaliteit keuze is {ranked[0]['name']}.\n"
            f"{format_product_lines(ranked, preferred_store, max_items=5)}",
            ranked[:4],
        )

    ranked = rank_by_value(scope_items, preferred_store)
    return (
        f"{scope_label} raad ik vooral deze producten aan voor prijs, kwaliteit en waarde:\n"
        f"{format_product_lines(ranked, preferred_store, max_items=5)}",
        ranked[:4],
    )


class BasketRequest(BaseModel):
    product_ids: List[int]
    location: Optional[str] = "Amsterdam"


class AIRequest(BaseModel):
    product_ids: List[int]
    budget: Optional[float] = None
    location: Optional[str] = "Amsterdam"


class AIChatRequest(BaseModel):
    session_id: Optional[str] = "default"
    message: str
    product_ids: Optional[List[int]] = []
    visible_product_ids: Optional[List[int]] = []
    active_store: Optional[str] = "all"
    active_category: Optional[str] = "Alle"
    sort_mode: Optional[str] = "price-asc"
    search_query: Optional[str] = ""


class UserCreate(BaseModel):
    email: str


class ShoppingListCreate(BaseModel):
    user_id: int
    name: str
    product_ids: List[int]


class PriceAlertCreate(BaseModel):
    user_id: int
    product_id: int
    target_price: float


@app.get("/")
def root():
    return {"message": "Grocery Discount API is running"}


@app.get("/health/data")
def health_data():
    return {
        "status": "ok" if PRODUCTS_CACHE else "not-loaded",
        "product_count": len(PRODUCTS_CACHE),
        "products_source": PRODUCTS_SOURCE,
        "validation_warning": PRODUCTS_VALIDATION_WARNING,
        "using_fallback": PRODUCTS_SOURCE.endswith("products_fallback.json"),
    }


@app.get("/stores")
def get_stores():
    return {"stores": STORES}


@app.get("/products")
def get_products(q: Optional[str] = None):
    products = [enrich_product(p) for p in load_products()]
    if not q:
        return {"products": products}

    query = q.lower().strip()
    filtered = [
        p for p in products
        if query in p["name"].lower()
        or query in p.get("category", "").lower()
        or any(query in tag.lower() for tag in p.get("tags", []))
        or query in p.get("reviewLabel", "").lower()
        or query in p.get("brandType", "").lower()
    ]
    return {"products": filtered}


@app.post("/basket/optimize")
def optimize_basket(request: BasketRequest):
    raw_products = load_products()
    items = [enrich_product(p) for p in raw_products if p["id"] in request.product_ids]
    return {"location": request.location, "selectedItems": items, "basket": build_basket(items)}


@app.post("/ai/recommend")
def ai_recommend(request: AIRequest):
    raw_products = load_products()
    items = [enrich_product(p) for p in raw_products if p["id"] in request.product_ids]
    basket = build_basket(items)
    insights = ai_deal_insights(items)

    budget_status = None
    if request.budget is not None:
        budget_status = {
            "budget": request.budget,
            "withinBudget": basket["splitTotal"] <= request.budget,
            "difference": round(request.budget - basket["splitTotal"], 2),
        }

    return {"location": request.location, "insights": insights, "basketSummary": basket, "budgetStatus": budget_status}


@app.get("/alerts/suggestions")
def alert_suggestions():
    return {
        "suggestions": [
            "Track eieren, melk en olijfolie en meld wanneer prijs daalt.",
            "Waarschuw voor prijsdalingen bij basisproducten met hoge prijs-kwaliteit.",
            "Highlight producten met lage kwaliteit maar lage prijs, zodat gebruikers bewust kiezen.",
        ]
    }


@app.post("/ai/chat")
def ai_chat(request: AIChatRequest):
    raw_products = load_products()
    enriched_all = [enrich_product(p) for p in raw_products]
    items = [p for p in enriched_all if p["id"] in request.product_ids]
    visible_items = [p for p in enriched_all if p["id"] in request.visible_product_ids]
    basket = build_basket(items) if items else None

    session_id = request.session_id or "default"
    history = CHAT_MEMORY.get(session_id, [])[-8:]
    context = SESSION_CONTEXT.get(session_id, {"last_products": []})

    reply, remembered_products = smart_chat_reply(
        request.message,
        items,
        enriched_all,
        basket,
        context,
        visible_items=visible_items,
        active_store=request.active_store,
        active_category=request.active_category,
        sort_mode=request.sort_mode,
        search_query=request.search_query,
    )

    CHAT_MEMORY[session_id] = history + [
        {"role": "user", "content": request.message},
        {"role": "assistant", "content": reply},
    ]
    SESSION_CONTEXT[session_id] = {"last_products": remembered_products}

    return {
        "reply": reply,
        "basket": basket,
        "session_id": session_id,
        "source": "local-json-data-ai-v2",
        "used_visible_products": len(visible_items),
        "used_selected_products": len(items),
    }


@app.post("/users/create")
def create_user(request: UserCreate):
    with Session(engine) as session:
        existing = session.exec(select(User).where(User.email == request.email)).first()
        if existing:
            return existing
        user = User(email=request.email)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


@app.get("/users/{user_id}")
def get_user(user_id: int):
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user


@app.post("/lists/create")
def create_list(request: ShoppingListCreate):
    with Session(engine) as session:
        user = session.get(User, request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        shopping_list = ShoppingList(user_id=request.user_id, name=request.name, product_ids=",".join(map(str, request.product_ids)))
        session.add(shopping_list)
        session.commit()
        session.refresh(shopping_list)
        return shopping_list


@app.get("/lists/{user_id}")
def get_lists(user_id: int):
    raw_products = load_products()
    with Session(engine) as session:
        lists = session.exec(select(ShoppingList).where(ShoppingList.user_id == user_id)).all()
        enriched_lists = []
        for shopping_list in lists:
            product_ids = [int(pid) for pid in shopping_list.product_ids.split(",") if pid]
            products = [enrich_product(p) for p in raw_products if p["id"] in product_ids]
            enriched_lists.append(
                {
                    "id": shopping_list.id,
                    "user_id": shopping_list.user_id,
                    "name": shopping_list.name,
                    "product_ids": product_ids,
                    "products": products,
                }
            )
        return enriched_lists


@app.delete("/lists/{user_id}/{list_id}")
def delete_list(user_id: int, list_id: int):
    with Session(engine) as session:
        shopping_list = session.get(ShoppingList, list_id)
        if not shopping_list or shopping_list.user_id != user_id:
            raise HTTPException(status_code=404, detail="List not found")
        session.delete(shopping_list)
        session.commit()
        return {"status": "deleted"}


@app.post("/alerts/create")
def create_price_alert(request: PriceAlertCreate):
    raw_products = load_products()
    with Session(engine) as session:
        user = session.get(User, request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        product = next((p for p in raw_products if p["id"] == request.product_id), None)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        alert = PriceAlert(user_id=request.user_id, product_id=request.product_id, target_price=request.target_price)
        session.add(alert)
        session.commit()
        session.refresh(alert)

        cheapest = get_cheapest_store(product)
        return {
            "id": alert.id,
            "user_id": alert.user_id,
            "product_id": alert.product_id,
            "product_name": product["name"],
            "target_price": alert.target_price,
            "current_lowest_price": cheapest["price"],
            "triggered": cheapest["price"] <= alert.target_price,
        }


@app.get("/alerts/{user_id}")
def get_user_alerts(user_id: int):
    raw_products = load_products()
    with Session(engine) as session:
        alerts = session.exec(select(PriceAlert).where(PriceAlert.user_id == user_id)).all()
        response = []
        for alert in alerts:
            product = next((p for p in raw_products if p["id"] == alert.product_id), None)
            if not product:
                continue
            current_price = get_cheapest_store(product)["price"]
            response.append(
                {
                    "id": alert.id,
                    "user_id": alert.user_id,
                    "product_id": alert.product_id,
                    "product_name": product["name"],
                    "target_price": alert.target_price,
                    "current_lowest_price": current_price,
                    "triggered": current_price <= alert.target_price,
                }
            )
        return response


@app.get("/alerts/check/{user_id}")
def check_alerts(user_id: int):
    alerts = get_user_alerts(user_id)
    triggered = [a for a in alerts if a["triggered"]]
    return {"alerts": alerts, "triggered": triggered}
