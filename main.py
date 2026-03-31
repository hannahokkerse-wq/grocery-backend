from fastapi import FastAPI, HTTPException, UploadFile, File
import os
import requests
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
    {"id": "freshmart", "name": "FreshMart", "distanceKm": 1.2},
    {"id": "valuefoods", "name": "ValueFoods", "distanceKm": 2.4},
    {"id": "greenbasket", "name": "GreenBasket", "distanceKm": 3.1},
]

PRODUCTS = [
    {
        "id": 1,
        "name": "Milk 1L",
        "category": "Dairy",
        "prices": {"freshmart": 1.89, "valuefoods": 1.59, "greenbasket": 1.79},
        "tags": ["weekly deal"],
        "substitute": "Store Brand Milk 1L",
    },
    {
        "id": 2,
        "name": "Eggs 12 pack",
        "category": "Dairy",
        "prices": {"freshmart": 3.49, "valuefoods": 2.99, "greenbasket": 3.29},
        "tags": ["coupon"],
        "substitute": "Eggs 6 pack x2",
    },
    {
        "id": 3,
        "name": "Chicken Breast 500g",
        "category": "Meat",
        "prices": {"freshmart": 5.99, "valuefoods": 6.49, "greenbasket": 5.59},
        "tags": ["protein", "popular"],
        "substitute": "Chicken Thighs 500g",
    },
    {
        "id": 4,
        "name": "Bananas 1kg",
        "category": "Produce",
        "prices": {"freshmart": 1.99, "valuefoods": 1.69, "greenbasket": 1.89},
        "tags": ["produce"],
        "substitute": "Loose Bananas",
    },
    {
        "id": 5,
        "name": "Rice 1kg",
        "category": "Pantry",
        "prices": {"freshmart": 2.79, "valuefoods": 2.49, "greenbasket": 2.59},
        "tags": ["pantry staple"],
        "substitute": "Store Brand Rice 1kg",
    },
    {
        "id": 6,
        "name": "Greek Yogurt 500g",
        "category": "Dairy",
        "prices": {"freshmart": 3.99, "valuefoods": 4.29, "greenbasket": 3.49},
        "tags": ["healthy"],
        "substitute": "Plain Yogurt 500g",
    },
    {
        "id": 7,
        "name": "Pasta 500g",
        "category": "Pantry",
        "prices": {"freshmart": 1.49, "valuefoods": 1.19, "greenbasket": 1.39},
        "tags": ["weekly deal"],
        "substitute": "Store Brand Pasta 500g",
    },
    {
        "id": 8,
        "name": "Olive Oil 1L",
        "category": "Pantry",
        "prices": {"freshmart": 9.99, "valuefoods": 8.99, "greenbasket": 9.49},
        "tags": ["tracked item"],
        "substitute": "Sunflower Oil 1L",
    },
]


def get_cheapest_store(product: Dict):
    cheapest_store_id = min(product["prices"], key=product["prices"].get)
    return {
        "storeId": cheapest_store_id,
        "price": product["prices"][cheapest_store_id],
    }


def build_basket(items: List[Dict]):
    per_store_totals = []
    for store in STORES:
        total = sum(item["prices"][store["id"]] for item in items)
        per_store_totals.append({**store, "total": round(total, 2)})

    single_store_best = min(per_store_totals, key=lambda x: x["total"])

    split_plan = []
    for item in items:
        cheapest = get_cheapest_store(item)
        split_plan.append(
            {
                "item": item["name"],
                "storeId": cheapest["storeId"],
                "price": cheapest["price"],
                "substitute": item["substitute"],
            }
        )

    split_total = round(sum(row["price"] for row in split_plan), 2)
    savings = round(single_store_best["total"] - split_total, 2)

    return {
        "perStoreTotals": per_store_totals,
        "singleStoreBest": single_store_best,
        "splitPlan": split_plan,
        "splitTotal": split_total,
        "savingsVsSingleStore": savings,
    }


def ai_deal_insights(items: List[Dict]):
    if not items:
        return [
            "Add a few grocery items and the AI assistant will suggest the cheapest basket.",
            "You can use this prototype to test savings recommendations before connecting real store data.",
        ]

    basket = build_basket(items)
    dairy_count = len([i for i in items if i["category"] == "Dairy"])
    pantry_count = len([i for i in items if i["category"] == "Pantry"])

    insights = [
        f"Best one-store option: {basket['singleStoreBest']['name']} at €{basket['singleStoreBest']['total']:.2f}.",
        f"Split shopping across stores drops the total to €{basket['splitTotal']:.2f}, saving €{basket['savingsVsSingleStore']:.2f}.",
    ]

    if dairy_count >= 2:
        insights.append("Your basket is dairy-heavy. Consider enabling coupon alerts for milk, eggs, and yogurt.")

    if pantry_count >= 2:
        insights.append("Pantry items are good candidates for bulk-buy recommendations when prices dip.")

    expensive = sorted(items, key=lambda i: get_cheapest_store(i)["price"], reverse=True)[0]
    insights.append(
        f"{expensive['name']} is your highest-cost item. AI substitute suggestion: {expensive['substitute']}."
    )

    return insights


class BasketRequest(BaseModel):
    product_ids: List[int]
    location: Optional[str] = "Amsterdam"


class AIRequest(BaseModel):
    product_ids: List[int]
    budget: Optional[float] = None
    location: Optional[str] = "Amsterdam"


@app.get("/")
def root():
    return {"message": "Grocery Discount API is running"}


@app.get("/stores")
def get_stores():
    return {"stores": STORES}


@app.get("/products")
def get_products(q: Optional[str] = None):
    if not q:
        return {"products": PRODUCTS}

    query = q.lower().strip()
    filtered = [
        p for p in PRODUCTS
        if query in p["name"].lower()
        or query in p["category"].lower()
        or any(query in tag.lower() for tag in p["tags"])
    ]
    return {"products": filtered}


@app.post("/basket/optimize")
def optimize_basket(request: BasketRequest):
    items = [p for p in PRODUCTS if p["id"] in request.product_ids]
    return {
        "location": request.location,
        "selectedItems": items,
        "basket": build_basket(items),
    }


@app.post("/ai/recommend")
def ai_recommend(request: AIRequest):
    items = [p for p in PRODUCTS if p["id"] in request.product_ids]
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
            "Track eggs, milk, and olive oil and alert when price drops by 10%.",
            "Notify users when pantry staples hit their lowest 30-day price.",
            "Recommend bulk-buy opportunities for dairy and pantry items.",
        ]
    }


# -------- REAL AI INTEGRATION --------
# Uses OpenAI-compatible API (can swap provider easily)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"


class AIChatRequest(BaseModel):
    session_id: Optional[str] = "default"
    message: str
    product_ids: Optional[List[int]] = []


CHAT_MEMORY: Dict[str, List[Dict[str, str]]] = {}


@app.post("/ai/chat")
def ai_chat(request: AIChatRequest):
    items = [p for p in PRODUCTS if p["id"] in request.product_ids]
    basket = build_basket(items) if items else None

    if not OPENAI_API_KEY:
        return {
            "reply": "AI not configured. Add OPENAI_API_KEY to enable smart assistant.",
            "fallback": ai_deal_insights(items)
        }

    session_id = request.session_id or "default"
    history = CHAT_MEMORY.get(session_id, [])[-8:]

    system_prompt = """
You are a grocery savings assistant.
You help users save money on groceries.
Always be practical, concise, and useful.
Prefer specific savings suggestions, substitutions, and shopping strategies.
"""

    user_context = f"""
User request: {request.message}
Selected items: {items}
Basket summary: {basket}

Respond with:
- savings advice
- cheaper substitutions
- best store strategy
- optional meal or budget tips
"""

    messages = [{"role": "system", "content": system_prompt}] + history + [
        {"role": "user", "content": user_context}
    ]

    try:
        response = requests.post(
            OPENAI_URL,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": messages,
                "temperature": 0.7,
            },
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        reply = data["choices"][0]["message"]["content"]

        CHAT_MEMORY[session_id] = history + [
            {"role": "user", "content": request.message},
            {"role": "assistant", "content": reply},
        ]

        return {
            "reply": reply,
            "basket": basket,
            "session_id": session_id
        }

    except Exception as e:
        return {
            "reply": "AI request failed. Falling back to built-in grocery tips.",
            "error": str(e),
            "fallback": ai_deal_insights(items)
        }


# -------- USER ACCOUNTS + SAVED LISTS (DB VERSION) --------

class UserCreate(BaseModel):
    email: str

class ShoppingListCreate(BaseModel):
    user_id: int
    name: str
    product_ids: List[int]

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
            product_ids=",".join(map(str, request.product_ids))
        )
        session.add(shopping_list)
        session.commit()
        session.refresh(shopping_list)
        return shopping_list

@app.get("/lists/{user_id}")
def get_lists(user_id: int):
    with Session(engine) as session:
        lists = session.exec(select(ShoppingList).where(ShoppingList.user_id == user_id)).all()
        enriched = []
        for shopping_list in lists:
            product_ids = [int(pid) for pid in shopping_list.product_ids.split(",") if pid]
            products = [p for p in PRODUCTS if p["id"] in product_ids]
            enriched.append({
                "id": shopping_list.id,
                "user_id": shopping_list.user_id,
                "name": shopping_list.name,
                "product_ids": product_ids,
                "products": products,
            })
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


# -------- PRICE ALERT SYSTEM (DB VERSION) --------

class PriceAlertCreate(BaseModel):
    user_id: int
    product_id: int
    target_price: float

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

        return {
            "id": alert.id,
            "user_id": alert.user_id,
            "product_id": alert.product_id,
            "product_name": product["name"],
            "target_price": alert.target_price,
            "current_lowest_price": get_cheapest_store(product)["price"],
            "triggered": get_cheapest_store(product)["price"] <= alert.target_price,
        }

@app.get("/alerts/{user_id}")
def get_user_alerts(user_id: int):
    with Session(engine) as session:
        alerts = session.exec(select(PriceAlert).where(PriceAlert.user_id == user_id)).all()
        response = []
        for alert in alerts:
            product = next((p for p in PRODUCTS if p["id"] == alert.product_id), None)
            if not product:
                continue
            current_price = get_cheapest_store(product)["price"]
            response.append({
                "id": alert.id,
                "user_id": alert.user_id,
                "product_id": alert.product_id,
                "product_name": product["name"],
                "target_price": alert.target_price,
                "current_lowest_price": current_price,
                "triggered": current_price <= alert.target_price,
            })
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


# -------- REAL DATA INGESTION (CSV/JSON) --------

import json

DATA_FILE = "grocery_data.json"

# Load data if exists
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        PRODUCTS = json.load(f)

@app.post("/data/upload")
def upload_data(file: UploadFile = File(...)):
    content = file.file.read().decode("utf-8")

    try:
        data = json.loads(content)
    except Exception:
        import csv
        reader = csv.DictReader(content.splitlines())
        data = []
        for i, row in enumerate(reader):
            data.append({
                "id": i + 1,
                "name": row.get("name"),
                "category": row.get("category", "Other"),
                "prices": {
                    "freshmart": float(row.get("freshmart", 0) or 0),
                    "valuefoods": float(row.get("valuefoods", 0) or 0),
                    "greenbasket": float(row.get("greenbasket", 0) or 0),
                },
                "tags": ["imported"],
                "substitute": row.get("substitute", "Generic alternative"),
            })

    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="Uploaded data must be a JSON array or valid CSV.")

    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

    global PRODUCTS
    PRODUCTS = data

    return {
        "status": "uploaded",
        "count": len(PRODUCTS)
    }

DATA_FILE = "grocery_data.json"

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        PRODUCTS = json.load(f)


@app.get("/data/status")
def data_status():
    return {
        "total_products": len(PRODUCTS),
        "source": "file" if os.path.exists(DATA_FILE) else "default"
    }
