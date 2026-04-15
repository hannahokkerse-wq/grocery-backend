from fastapi import FastAPI, HTTPException
import os
import json
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from sqlmodel import SQLModel, Field, Session, create_engine, select
from contextlib import asynccontextmanager
from datetime import date

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./grocery_discount.db")
engine = create_engine(DATABASE_URL, echo=False)

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "products.json"


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
]

STORE_NAME_MAP = {store["id"]: store["name"] for store in STORES}
CHAT_MEMORY: Dict[str, List[Dict[str, str]]] = {}
SESSION_CONTEXT: Dict[str, Dict] = {}


def load_products() -> List[Dict]:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_products(products: List[Dict]) -> None:
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def get_cheapest_store(product: Dict):
    cheapest_store_id = min(product["prices"], key=product["prices"].get)
    return {
        "storeId": cheapest_store_id,
        "price": product["prices"][cheapest_store_id],
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
        total = sum(item["prices"][store["id"]] for item in items)
        per_store_totals.append({**store, "total": round(total, 2)})

    single_store_best = (
        min(per_store_totals, key=lambda x: x["total"]) if per_store_totals else None
    )

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
        f"Laagste kwaliteitsscore: {weakest_item['name']} ({weakest_item.get('qualityScore', 0)}/10). Let hier extra op.",
    ]

    if basket["savingsVsSingleStore"] > 0:
        insights.append(
            f"Door slim te splitsen tussen winkels bespaar je €{basket['savingsVsSingleStore']:.2f}."
        )

    return insights


def format_product_list(items: List[Dict], max_items: int = 4):
    return ", ".join(item["name"] for item in items[:max_items])


def available_stores_for_product(product: Dict) -> List[str]:
    prices = product.get("prices", {})
    return [
        STORE_NAME_MAP[store_id]
        for store_id, price in prices.items()
        if price is not None and store_id in STORE_NAME_MAP
    ]


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

    return ", ".join(parts)


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
    remembered_products = session_context.get("last_products", []) if session_context else []
    visible_items = visible_items or []

    reference_words = [
        "deze producten", "die producten", "deze", "die",
        "deze keuzes", "die keuzes", "deze lijst",
        "wat ik nu zie", "wat nu zichtbaar is"
    ]
    use_remembered = any(term in msg for term in reference_words)

    if use_remembered and remembered_products:
        scope_items = remembered_products
    elif items:
        scope_items = items
    elif visible_items:
        scope_items = visible_items
    else:
        scope_items = all_products

    scope_basket = basket if items and not use_remembered else build_basket(scope_items)
    best_value_item = max(scope_items, key=lambda i: i.get("valueScore", 0))
    best_quality_item = max(scope_items, key=lambda i: i.get("qualityScore", 0))
    cheapest_item = min(scope_items, key=lambda i: get_cheapest_store(i)["price"])
    weakest_item = min(scope_items, key=lambda i: i.get("qualityScore", 0))

    cheapest_sorted = sorted(scope_items, key=lambda i: get_cheapest_store(i)["price"])
    best_value_sorted = sorted(scope_items, key=lambda i: i.get("valueScore", 0), reverse=True)
    best_quality_sorted = sorted(scope_items, key=lambda i: i.get("qualityScore", 0), reverse=True)

    visible_summary = get_visible_scope_summary(
        visible_items=visible_items,
        active_store=active_store,
        active_category=active_category,
        sort_mode=sort_mode,
        search_query=search_query or "",
    )

    if any(word in msg for word in ["winkel", "winkels", "supermarkt", "supermarkten", "beschikbaar"]):
        if visible_items and not items and not use_remembered:
            return f"Binnen de huidige filterselectie ({visible_summary}) geldt: " + make_store_answer(scope_items[:4]), scope_items[:4]
        return make_store_answer(scope_items[:4]), scope_items[:4]

    if any(word in msg for word in ["aanbieding", "bonus", "actie"]):
        promo_items = [item for item in scope_items if any(tag.lower() in ["bonus", "actie"] for tag in item.get("tags", []))]
        if promo_items:
            if visible_items and not items and not use_remembered:
                intro = f"Binnen de huidige filterselectie ({visible_summary}) zijn de producten in de aanbieding: "
            else:
                intro = "De producten in de aanbieding zijn: "
            return f"{intro}{format_product_list(promo_items)}.", promo_items[:4]
        return "Ik zie op dit moment geen producten in de aanbieding binnen deze selectie.", []

    if any(word in msg for word in ["goedkoop", "goedkope", "besparen", "goedkoopst"]):
        if visible_items and not items and not use_remembered:
            intro = f"Binnen de huidige filterselectie ({visible_summary}) zijn de goedkoopste producten: "
        elif items:
            intro = "Binnen je huidige selectie zijn de goedkoopste producten: "
        else:
            intro = "De goedkoopste producten zijn: "
        return (
            f"{intro}{format_product_list(cheapest_sorted)}. "
            f"De allergoedkoopste keuze is {cheapest_item['name']} voor €{get_cheapest_store(cheapest_item)['price']:.2f}. "
            f"De voordeligste supermarkt voor deze scope is {scope_basket['singleStoreBest']['name']}.",
            cheapest_sorted[:4],
        )

    if any(word in msg for word in ["prijs-kwaliteit", "waarde", "beste keuze"]):
        if visible_items and not items and not use_remembered:
            intro = f"Binnen de huidige filterselectie ({visible_summary}) zijn de beste prijs-kwaliteit producten: "
        elif items:
            intro = "Binnen je huidige selectie zijn de beste prijs-kwaliteit producten: "
        else:
            intro = "De beste prijs-kwaliteit producten zijn: "
        return (
            f"{intro}{format_product_list(best_value_sorted)}. "
            f"De sterkste keuze is {best_value_item['name']} met een waarde-score van {best_value_item.get('valueScore', 0)}/10.",
            best_value_sorted[:4],
        )

    if any(word in msg for word in ["kwaliteit", "beste kwaliteit", "goedste"]):
        if visible_items and not items and not use_remembered:
            intro = f"Binnen de huidige filterselectie ({visible_summary}) zijn de producten met de hoogste kwaliteit: "
        elif items:
            intro = "Binnen je huidige selectie zijn de producten met de hoogste kwaliteit: "
        else:
            intro = "De producten met de hoogste kwaliteit zijn: "
        return (
            f"{intro}{format_product_list(best_quality_sorted)}. "
            f"De hoogste kwaliteitsscore is {best_quality_item['name']} met {best_quality_item.get('qualityScore', 0)}/10. "
            f"De laagste kwaliteitsscore is {weakest_item['name']} met {weakest_item.get('qualityScore', 0)}/10.",
            best_quality_sorted[:4],
        )

    if any(word in msg for word in ["gezond", "gezondere", "gezondst"]):
        healthy_items = [
            item for item in scope_items
            if "gezond" in [tag.lower() for tag in item.get("tags", [])]
            or item.get("category") in ["Groente & Fruit", "Zuivel"]
        ]
        healthy_sorted = sorted(healthy_items, key=lambda i: i.get("qualityScore", 0), reverse=True)
        if healthy_sorted:
            if visible_items and not items and not use_remembered:
                intro = f"Binnen de huidige filterselectie ({visible_summary}) zijn de gezondste keuzes: "
            elif items:
                intro = "Binnen je huidige selectie zijn de gezondste keuzes: "
            else:
                intro = "De gezondste keuzes zijn: "
            return (
                f"{intro}{format_product_list(healthy_sorted)}. "
                f"De beste gezonde keuze is {healthy_sorted[0]['name']} met een kwaliteitsscore van {healthy_sorted[0].get('qualityScore', 0)}/10.",
                healthy_sorted[:4],
            )
        return "Ik zie in de huidige scope niet direct gezonde keuzes.", []

    if any(word in msg for word in ["mandje", "basket", "totaal"]):
        if items:
            return (
                f"Je geselecteerde mandje heeft nu een goedkoopste totaalprijs van €{scope_basket['splitTotal']:.2f}. "
                f"De gemiddelde kwaliteit is {scope_basket['averageQualityScore']}/10 en de gemiddelde prijs-kwaliteit is {scope_basket['averageValueScore']}/10.",
                items[:4],
            )
        if visible_items:
            return (
                f"Binnen de huidige filterselectie ({visible_summary}) is de voordeligste supermarkt "
                f"{scope_basket['singleStoreBest']['name']} met een totaal van €{scope_basket['singleStoreBest']['total']:.2f}. "
                f"Als je producten selecteert, kan ik je mandje nog specifieker analyseren.",
                visible_items[:4],
            )
        return (
            f"Over alle producten bekeken is {scope_basket['singleStoreBest']['name']} de goedkoopste supermarkt. "
            f"Als je producten selecteert, kan ik je mandje specifieker analyseren.",
            [],
        )

    if any(word in msg for word in ["wat zie ik", "wat staat er", "wat is zichtbaar"]):
        if visible_items:
            return (
                f"Binnen de huidige filterselectie vallen {len(visible_items)} producten met deze context: {visible_summary}. "
                f"De goedkoopste keuze is {cheapest_item['name']} en de beste prijs-kwaliteit keuze is {best_value_item['name']}.",
                visible_items[:4],
            )
        return "Ik heb op dit moment geen filtercontext ontvangen.", []

    return (
        f"Op basis van de huidige context raad ik {best_value_item['name']} aan voor prijs-kwaliteit, "
        f"{best_quality_item['name']} voor kwaliteit en {cheapest_item['name']} als goedkoopste keuze. "
        f"De voordeligste supermarkt voor deze scope is {scope_basket['singleStoreBest']['name']}.",
        scope_items[:4],
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
        or query in p["category"].lower()
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

    return {
        "location": request.location,
        "insights": insights,
        "basketSummary": basket,
        "budgetStatus": budget_status,
    }


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
        "source": "local-json-data-v1",
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

        shopping_list = ShoppingList(
            user_id=request.user_id,
            name=request.name,
            product_ids=",".join(map(str, request.product_ids)),
        )
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

        alert = PriceAlert(
            user_id=request.user_id,
            product_id=request.product_id,
            target_price=request.target_price,
        )
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
