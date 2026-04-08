from fastapi import FastAPI, HTTPException
import os
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from sqlmodel import SQLModel, Field, Session, create_engine, select
from contextlib import asynccontextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./grocery_discount.db")
engine = create_engine(DATABASE_URL, echo=False)


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

PRODUCTS = [
    {
        "id": 1,
        "name": "Halfvolle melk 1L",
        "category": "Zuivel",
        "prices": {"ah": 1.89, "jumbo": 1.79, "lidl": 1.55, "aldi": 1.49},
        "tags": ["bonus"],
        "substitute": "Huismerk melk 1L",
        "qualityScore": 7.8,
        "valueScore": 8.9,
        "brandType": "huismerk",
        "reviewLabel": "goede prijs-kwaliteit",
    },
    {
        "id": 2,
        "name": "Eieren 12 stuks",
        "category": "Zuivel",
        "prices": {"ah": 3.49, "jumbo": 3.19, "lidl": 2.89, "aldi": 2.79},
        "tags": ["actie"],
        "substitute": "Eieren 10 stuks",
        "qualityScore": 8.2,
        "valueScore": 8.7,
        "brandType": "huismerk",
        "reviewLabel": "betrouwbare basiskeuze",
    },
    {
        "id": 3,
        "name": "Kipfilet 500g",
        "category": "Vlees",
        "prices": {"ah": 5.99, "jumbo": 5.79, "lidl": 5.49, "aldi": 5.29},
        "tags": ["populair"],
        "substitute": "Kippendijfilet 500g",
        "qualityScore": 7.2,
        "valueScore": 8.1,
        "brandType": "huismerk",
        "reviewLabel": "prima voor dagelijkse maaltijden",
    },
    {
        "id": 4,
        "name": "Bananen 1kg",
        "category": "Groente & Fruit",
        "prices": {"ah": 1.99, "jumbo": 1.89, "lidl": 1.69, "aldi": 1.59},
        "tags": ["vers"],
        "substitute": "Losse bananen",
        "qualityScore": 8.4,
        "valueScore": 9.0,
        "brandType": "vers",
        "reviewLabel": "sterke prijs-kwaliteit",
    },
    {
        "id": 5,
        "name": "Witte rijst 1kg",
        "category": "Houdbaar",
        "prices": {"ah": 2.79, "jumbo": 2.59, "lidl": 2.29, "aldi": 2.19},
        "tags": ["basis"],
        "substitute": "Houdbaar huismerk rijst",
        "qualityScore": 7.5,
        "valueScore": 8.8,
        "brandType": "huismerk",
        "reviewLabel": "betaalbare voorraadkeuze",
    },
    {
        "id": 6,
        "name": "Griekse yoghurt 500g",
        "category": "Zuivel",
        "prices": {"ah": 3.99, "jumbo": 3.79, "lidl": 3.39, "aldi": 3.29},
        "tags": ["gezond"],
        "substitute": "Magere yoghurt",
        "qualityScore": 8.6,
        "valueScore": 8.7,
        "brandType": "huismerk",
        "reviewLabel": "goede smaak en structuur",
    },
    {
        "id": 7,
        "name": "Pasta 500g",
        "category": "Houdbaar",
        "prices": {"ah": 1.49, "jumbo": 1.39, "lidl": 1.19, "aldi": 1.09},
        "tags": ["bonus"],
        "substitute": "Volkoren pasta",
        "qualityScore": 7.0,
        "valueScore": 9.2,
        "brandType": "huismerk",
        "reviewLabel": "zeer goedkoop en prima",
    },
    {
        "id": 8,
        "name": "Olijfolie 1L",
        "category": "Houdbaar",
        "prices": {"ah": 9.99, "jumbo": 9.49, "lidl": 8.99, "aldi": 8.79},
        "tags": ["actie"],
        "substitute": "Zonnebloemolie",
        "qualityScore": 8.8,
        "valueScore": 7.9,
        "brandType": "A-merk alternatief",
        "reviewLabel": "hogere kwaliteit, minder goedkoop",
    },
    {
        "id": 9,
        "name": "Brood volkoren",
        "category": "Brood",
        "prices": {"ah": 2.49, "jumbo": 2.39, "lidl": 1.99, "aldi": 1.89},
        "tags": ["dagelijks"],
        "substitute": "Wit brood",
        "qualityScore": 7.7,
        "valueScore": 8.8,
        "brandType": "huismerk",
        "reviewLabel": "prima basisbrood",
    },
    {
        "id": 10,
        "name": "Appels 1kg",
        "category": "Groente & Fruit",
        "prices": {"ah": 2.99, "jumbo": 2.79, "lidl": 2.49, "aldi": 2.39},
        "tags": ["vers"],
        "substitute": "Peren 1kg",
        "qualityScore": 8.5,
        "valueScore": 8.9,
        "brandType": "vers",
        "reviewLabel": "fris en goede kwaliteit",
    },
    {
        "id": 11,
        "name": "Aardappelen 2kg",
        "category": "Groente & Fruit",
        "prices": {"ah": 3.99, "jumbo": 3.79, "lidl": 3.49, "aldi": 3.29},
        "tags": ["basis"],
        "substitute": "Zoete aardappel",
        "qualityScore": 7.9,
        "valueScore": 8.8,
        "brandType": "vers",
        "reviewLabel": "goede budgetkeuze",
    },
    {
        "id": 12,
        "name": "Kaas jong belegen 400g",
        "category": "Zuivel",
        "prices": {"ah": 4.99, "jumbo": 4.79, "lidl": 4.29, "aldi": 4.19},
        "tags": ["bonus"],
        "substitute": "30+ kaas",
        "qualityScore": 8.3,
        "valueScore": 8.5,
        "brandType": "huismerk",
        "reviewLabel": "goede balans tussen smaak en prijs",
    },
    {
        "id": 13,
        "name": "Frisdrank cola 1.5L",
        "category": "Drinken",
        "prices": {"ah": 1.89, "jumbo": 1.79, "lidl": 1.49, "aldi": 1.39},
        "tags": ["actie"],
        "substitute": "Cola zero",
        "qualityScore": 6.8,
        "valueScore": 8.6,
        "brandType": "huismerk",
        "reviewLabel": "goedkoop maar smaak is wisselend",
    },
    {
        "id": 14,
        "name": "Sinaasappelsap 1L",
        "category": "Drinken",
        "prices": {"ah": 2.49, "jumbo": 2.29, "lidl": 1.99, "aldi": 1.89},
        "tags": ["vers"],
        "substitute": "Appelsap",
        "qualityScore": 7.9,
        "valueScore": 8.4,
        "brandType": "huismerk",
        "reviewLabel": "frisse smaak, nette prijs",
    },
    {
        "id": 15,
        "name": "Tomaten 500g",
        "category": "Groente & Fruit",
        "prices": {"ah": 2.19, "jumbo": 2.09, "lidl": 1.79, "aldi": 1.69},
        "tags": ["vers"],
        "substitute": "Cherry tomaat",
        "qualityScore": 8.1,
        "valueScore": 8.8,
        "brandType": "vers",
        "reviewLabel": "mooie prijs-kwaliteit voor salade en koken",
    },
]


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
                "substitute": item["substitute"],
                "qualityScore": item.get("qualityScore"),
                "valueScore": item.get("valueScore"),
            }
        )

    split_total = round(sum(row["price"] for row in split_plan), 2) if split_plan else 0
    savings = (
        round(single_store_best["total"] - split_total, 2)
        if single_store_best
        else 0
    )

    avg_quality = (
        round(sum(item.get("qualityScore", 0) for item in items) / len(items), 1)
        if items
        else 0
    )

    avg_value = (
        round(sum(item.get("valueScore", 0) for item in items) / len(items), 1)
        if items
        else 0
    )

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

    insights = [
        f"Goedkoopste totaaloptie: €{basket['splitTotal']:.2f}.",
        f"Gemiddelde kwaliteit van je mandje: {basket['averageQualityScore']}/10.",
        f"Gemiddelde prijs-kwaliteit van je mandje: {basket['averageValueScore']}/10.",
    ]

    best_quality_item = max(items, key=lambda i: i.get("qualityScore", 0))
    best_value_item = max(items, key=lambda i: i.get("valueScore", 0))
    weakest_item = min(items, key=lambda i: i.get("qualityScore", 0))

    insights.append(
        f"Beste kwaliteit in je mandje: {best_quality_item['name']} ({best_quality_item.get('qualityScore', 0)}/10)."
    )
    insights.append(
        f"Beste prijs-kwaliteit: {best_value_item['name']} ({best_value_item.get('valueScore', 0)}/10)."
    )
    insights.append(
        f"Laagste kwaliteitsscore: {weakest_item['name']} ({weakest_item.get('qualityScore', 0)}/10). Let hier extra op."
    )

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


def smart_chat_reply(
    message: str,
    items: List[Dict],
    basket: Optional[Dict] = None,
    session_context: Optional[Dict] = None,
):
    msg = message.lower().strip()

    remembered_products = []
    if session_context:
        remembered_products = session_context.get("last_products", [])

    reference_words = [
        "deze producten",
        "die producten",
        "deze",
        "die",
        "deze keuzes",
        "die keuzes",
    ]

    use_remembered = any(term in msg for term in reference_words)

    if use_remembered and remembered_products:
        scope_items = remembered_products
    else:
        scope_items = items if items else [enrich_product(p) for p in PRODUCTS]

    scope_basket = basket if items and not use_remembered else build_basket(scope_items)

    best_value_item = max(scope_items, key=lambda i: i.get("valueScore", 0))
    best_quality_item = max(scope_items, key=lambda i: i.get("qualityScore", 0))
    cheapest_item = min(scope_items, key=lambda i: get_cheapest_store(i)["price"])
    weakest_item = min(scope_items, key=lambda i: i.get("qualityScore", 0))

    cheapest_sorted = sorted(scope_items, key=lambda i: get_cheapest_store(i)["price"])
    best_value_sorted = sorted(
        scope_items, key=lambda i: i.get("valueScore", 0), reverse=True
    )
    best_quality_sorted = sorted(
        scope_items, key=lambda i: i.get("qualityScore", 0), reverse=True
    )

    response_products = scope_items[:4]

    if any(
        word in msg
        for word in ["winkel", "winkels", "supermarkt", "supermarkten", "beschikbaar"]
    ):
        return make_store_answer(response_products), response_products

    if any(word in msg for word in ["aanbieding", "bonus", "actie"]):
        promo_items = [
            item
            for item in scope_items
            if any(tag.lower() in ["bonus", "actie"] for tag in item.get("tags", []))
        ]
        if promo_items:
            return (
                f"De producten in de aanbieding zijn: {format_product_list(promo_items)}.",
                promo_items[:4],
            )
        return "Ik zie op dit moment geen producten in de aanbieding.", []

    if any(word in msg for word in ["goedkoop", "goedkope", "besparen", "goedkoopst"]):
        return (
            f"De goedkoopste producten zijn: {format_product_list(cheapest_sorted)}. "
            f"De allergoedkoopste keuze is {cheapest_item['name']} voor "
            f"€{get_cheapest_store(cheapest_item)['price']:.2f}. "
            f"Als je vooral wilt besparen, is {scope_basket['singleStoreBest']['name']} "
            f"nu de voordeligste supermarkt.",
            cheapest_sorted[:4],
        )

    if any(word in msg for word in ["prijs-kwaliteit", "waarde", "beste keuze"]):
        return (
            f"De beste prijs-kwaliteit producten zijn: {format_product_list(best_value_sorted)}. "
            f"De sterkste keuze is {best_value_item['name']} met een waarde-score van "
            f"{best_value_item.get('valueScore', 0)}/10.",
            best_value_sorted[:4],
        )

    if any(word in msg for word in ["kwaliteit", "beste kwaliteit", "goedste"]):
        return (
            f"De producten met de hoogste kwaliteit zijn: {format_product_list(best_quality_sorted)}. "
            f"De hoogste kwaliteitsscore is {best_quality_item['name']} met "
            f"{best_quality_item.get('qualityScore', 0)}/10. "
            f"De laagste kwaliteitsscore is {weakest_item['name']} met "
            f"{weakest_item.get('qualityScore', 0)}/10.",
            best_quality_sorted[:4],
        )

    if any(word in msg for word in ["gezond", "gezondere", "gezondst"]):
        healthy_items = [
            item
            for item in scope_items
            if "gezond" in [tag.lower() for tag in item.get("tags", [])]
            or item.get("category") in ["Groente & Fruit", "Zuivel"]
        ]
        healthy_sorted = sorted(
            healthy_items, key=lambda i: i.get("qualityScore", 0), reverse=True
        )
        if healthy_sorted:
            return (
                f"De gezondste keuzes zijn: {format_product_list(healthy_sorted)}. "
                f"De beste gezonde keuze is {healthy_sorted[0]['name']} "
                f"met een kwaliteitsscore van {healthy_sorted[0].get('qualityScore', 0)}/10.",
                healthy_sorted[:4],
            )
        return "Ik zie in de huidige dataset niet direct gezonde keuzes.", []

    if any(word in msg for word in ["mandje", "basket", "totaal"]):
        if items:
            return (
                f"Je geselecteerde mandje heeft nu een goedkoopste totaalprijs van "
                f"€{scope_basket['splitTotal']:.2f}. "
                f"De gemiddelde kwaliteit is {scope_basket['averageQualityScore']}/10 "
                f"en de gemiddelde prijs-kwaliteit is {scope_basket['averageValueScore']}/10.",
                items[:4],
            )
        return (
            f"Over alle producten bekeken is {scope_basket['singleStoreBest']['name']} "
            f"de goedkoopste supermarkt. Als je producten selecteert, kan ik je mandje specifieker analyseren.",
            [],
        )

    return (
        f"Mijn advies is om vooral te kijken naar {best_value_item['name']} voor prijs-kwaliteit, "
        f"{best_quality_item['name']} voor kwaliteit en {cheapest_item['name']} als goedkoopste keuze. "
        f"Op totaalniveau is {scope_basket['singleStoreBest']['name']} momenteel de voordeligste supermarkt.",
        response_products,
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


CHAT_MEMORY: Dict[str, List[Dict[str, str]]] = {}
SESSION_CONTEXT: Dict[str, Dict] = {}


@app.get("/")
def root():
    return {"message": "Grocery Discount API is running"}


@app.get("/stores")
def get_stores():
    return {"stores": STORES}


@app.get("/products")
def get_products(q: Optional[str] = None):
    products = [enrich_product(p) for p in PRODUCTS]

    if not q:
        return {"products": products}

    query = q.lower().strip()
    filtered = [
        p
        for p in products
        if query in p["name"].lower()
        or query in p["category"].lower()
        or any(query in tag.lower() for tag in p["tags"])
        or query in p.get("reviewLabel", "").lower()
        or query in p.get("brandType", "").lower()
    ]
    return {"products": filtered}


@app.post("/basket/optimize")
def optimize_basket(request: BasketRequest):
    items = [enrich_product(p) for p in PRODUCTS if p["id"] in request.product_ids]
    return {
        "location": request.location,
        "selectedItems": items,
        "basket": build_basket(items),
    }


@app.post("/ai/recommend")
def ai_recommend(request: AIRequest):
    items = [enrich_product(p) for p in PRODUCTS if p["id"] in request.product_ids]
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
    items = [enrich_product(p) for p in PRODUCTS if p["id"] in request.product_ids]
    basket = build_basket(items) if items else None

    session_id = request.session_id or "default"
    history = CHAT_MEMORY.get(session_id, [])[-8:]
    context = SESSION_CONTEXT.get(session_id, {"last_products": []})

    reply, remembered_products = smart_chat_reply(
        request.message, items, basket, context
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
        "source": "local-smart-ai-v2",
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
    with Session(engine) as session:
        lists = session.exec(
            select(ShoppingList).where(ShoppingList.user_id == user_id)
        ).all()
        enriched = []
        for shopping_list in lists:
            product_ids = [
                int(pid) for pid in shopping_list.product_ids.split(",") if pid
            ]
            products = [enrich_product(p) for p in PRODUCTS if p["id"] in product_ids]
            enriched.append(
                {
                    "id": shopping_list.id,
                    "user_id": shopping_list.user_id,
                    "name": shopping_list.name,
                    "product_ids": product_ids,
                    "products": products,
                }
            )
        return enriched


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
    with Session(engine) as session:
        user = session.get(User, request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        product = next((p for p in PRODUCTS if p["id"] == request.product_id), None)
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
    with Session(engine) as session:
        alerts = session.exec(
            select(PriceAlert).where(PriceAlert.user_id == user_id)
        ).all()
        response = []
        for alert in alerts:
            product = next((p for p in PRODUCTS if p["id"] == alert.product_id), None)
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


@app.delete("/alerts/{alert_id}")
def delete_alert(alert_id: int):
    with Session(engine) as session:
        alert = session.get(PriceAlert, alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        session.delete(alert)
        session.commit()
        return {"status": "deleted"}
