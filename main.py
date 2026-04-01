from fastapi import FastAPI, HTTPException, UploadFile, File
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
    {"id": 1, "name": "Halfvolle melk 1L", "category": "Zuivel", "prices": {"ah": 1.89, "jumbo": 1.79, "lidl": 1.55, "aldi": 1.49}, "tags": ["bonus"], "substitute": "Huismerk melk 1L"},
    {"id": 2, "name": "Eieren 12 stuks", "category": "Zuivel", "prices": {"ah": 3.49, "jumbo": 3.19, "lidl": 2.89, "aldi": 2.79}, "tags": ["actie"], "substitute": "Eieren 10 stuks"},
    {"id": 3, "name": "Kipfilet 500g", "category": "Vlees", "prices": {"ah": 5.99, "jumbo": 5.79, "lidl": 5.49, "aldi": 5.29}, "tags": ["populair"], "substitute": "Kippendijfilet 500g"},
    {"id": 4, "name": "Bananen 1kg", "category": "Groente & Fruit", "prices": {"ah": 1.99, "jumbo": 1.89, "lidl": 1.69, "aldi": 1.59}, "tags": ["vers"], "substitute": "Losse bananen"},
    {"id": 5, "name": "Witte rijst 1kg", "category": "Houdbaar", "prices": {"ah": 2.79, "jumbo": 2.59, "lidl": 2.29, "aldi": 2.19}, "tags": ["basis"], "substitute": "Zilvervliesrijst"},
    {"id": 6, "name": "Griekse yoghurt 500g", "category": "Zuivel", "prices": {"ah": 3.99, "jumbo": 3.79, "lidl": 3.39, "aldi": 3.29}, "tags": ["gezond"], "substitute": "Magere yoghurt"},
    {"id": 7, "name": "Pasta 500g", "category": "Houdbaar", "prices": {"ah": 1.49, "jumbo": 1.39, "lidl": 1.19, "aldi": 1.09}, "tags": ["bonus"], "substitute": "Volkoren pasta"},
    {"id": 8, "name": "Olijfolie 1L", "category": "Houdbaar", "prices": {"ah": 9.99, "jumbo": 9.49, "lidl": 8.99, "aldi": 8.79}, "tags": ["actie"], "substitute": "Zonnebloemolie"},
    {"id": 9, "name": "Brood volkoren", "category": "Brood", "prices": {"ah": 2.49, "jumbo": 2.39, "lidl": 1.99, "aldi": 1.89}, "tags": ["dagelijks"], "substitute": "Wit brood"},
    {"id": 10, "name": "Appels 1kg", "category": "Groente & Fruit", "prices": {"ah": 2.99, "jumbo": 2.79, "lidl": 2.49, "aldi": 2.39}, "tags": ["vers"], "substitute": "Peren 1kg"},
    {"id": 11, "name": "Aardappelen 2kg", "category": "Groente & Fruit", "prices": {"ah": 3.99, "jumbo": 3.79, "lidl": 3.49, "aldi": 3.29}, "tags": ["basis"], "substitute": "Zoete aardappel"},
    {"id": 12, "name": "Kaas jong belegen 400g", "category": "Zuivel", "prices": {"ah": 4.99, "jumbo": 4.79, "lidl": 4.29, "aldi": 4.19}, "tags": ["bonus"], "substitute": "30+ kaas"},
    {"id": 13, "name": "Frisdrank cola 1.5L", "category": "Drinken", "prices": {"ah": 1.89, "jumbo": 1.79, "lidl": 1.49, "aldi": 1.39}, "tags": ["actie"], "substitute": "Cola zero"},
    {"id": 14, "name": "Sinaasappelsap 1L", "category": "Drinken", "prices": {"ah": 2.49, "jumbo": 2.29, "lidl": 1.99, "aldi": 1.89}, "tags": ["vers"], "substitute": "Appelsap"},
    {"id": 15, "name": "Tomaten 500g", "category": "Groente & Fruit", "prices": {"ah": 2.19, "jumbo": 2.09, "lidl": 1.79, "aldi": 1.69}, "tags": ["vers"], "substitute": "Cherry tomaat"}
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

    single_store_best = min(per_store_totals, key=lambda x: x["total"]) if per_store_totals else None

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
    savings = round((single_store_best["total"] - split_total), 2) if single_store_best else 0

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
    dairy_count = len([i for i in items if i["category"] == "Zuivel"])
    pantry_count = len([i for i in items if i["category"] == "Houdbaar"])

    insights = [
        f"Beste supermarkt voor alles samen: {basket['singleStoreBest']['name']} voor €{basket['singleStoreBest']['total']:.2f}.",
        f"Als je slim splitst tussen winkels betaal je €{basket['splitTotal']:.2f}, en bespaar je €{basket['savingsVsSingleStore']:.2f}.",
    ]

    if dairy_count >= 2:
        insights.append("Je mandje bevat veel zuivel. Let op bonusacties voor melk, eieren, yoghurt en kaas.")

    if pantry_count >= 2:
        insights.append("Houdbare producten zijn slim om in bulk te kopen als ze in de aanbieding zijn.")

    expensive = sorted(items, key=lambda i: get_cheapest_store(i)["price"], reverse=True)[0]
    insights.append(
        f"{expensive['name']} is je duurste product. Slim alternatief: {expensive['substitute']}."
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
            "Track eieren, melk en olijfolie en stuur een alert bij 10% prijsdaling.",
            "Geef een melding wanneer houdbare basisproducten hun laagste prijs bereiken.",
            "Aanbevelingen voor bulkinkopen bij bonusacties.",
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
            "reply": "AI is nog niet gekoppeld. Voeg OPENAI_API_KEY toe om slimme supermarkt-assistent te activeren.",
            "fallback": ai_deal_insights(items)
        }

    session_id = request.session_id or "default"
    history = CHAT_MEMORY.get(session_id, [])[-8:]

    system_prompt = """
You are a grocery savings assistant for Dutch supermarkets.
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
            "reply": "AI-aanvraag mislukt. Ik val terug op ingebouwde bespaartips.",
            "error": str(e),
            "fallback": ai_deal_insights(items)
        }


DATA_FILE = "grocery_data.json"

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
                "category": row.get("category", "Overig"),
                "prices": {
                    "ah": float(row.get("ah", 0) or 0),
                    "jumbo": float(row.get("jumbo", 0) or 0),
                    "lidl": float(row.get("lidl", 0) or 0),
                    "aldi": float(row.get("aldi", 0) or 0),
                },
                "tags": ["imported"],
                "substitute": row.get("substitute", "Goedkoper alternatief"),
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


@app.get("/data/status")
def data_status():
    return {
        "total_products": len(PRODUCTS),
        "source": "file" if os.path.exists(DATA_FILE) else "default"
    }
