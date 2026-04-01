from fastapi import FastAPI, HTTPException
import os
import requests
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import json

app = FastAPI(title="Grocery Discount API")

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

DATA_FILE = "grocery_data.json"

if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, "r") as f:
            PRODUCTS = json.load(f)
    except Exception:
        pass


def get_cheapest_store(product: Dict):
    cheapest_store_id = min(product["prices"], key=product["prices"].get)
    return {
        "storeId": cheapest_store_id,
        "price": product["prices"][cheapest_store_id],
    }


def build_basket(items: List[Dict]):
    if not items:
        return {
            "perStoreTotals": [],
            "singleStoreBest": None,
            "splitPlan": [],
            "splitTotal": 0,
            "savingsVsSingleStore": 0,
        }

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


class AIChatRequest(BaseModel):
    session_id: Optional[str] = "default"
    message: str
    product_ids: Optional[List[int]] = []


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


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
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


@app.get("/data/status")
def data_status():
    return {
        "total_products": len(PRODUCTS),
        "source": "file" if os.path.exists(DATA_FILE) else "default"
    }
