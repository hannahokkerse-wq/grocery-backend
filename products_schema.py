from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

StoreId = Literal["ah", "jumbo", "lidl", "aldi", "plus", "dirk"]

REQUIRED_STORES = {"ah", "jumbo", "lidl", "aldi", "plus", "dirk"}

ALLOWED_CATEGORIES = {
    "Zuivel",
    "Groente & Fruit",
    "Brood",
    "Houdbaar",
    "Ontbijt",
    "Drinken",
    "Snacks",
    "Diepvries",
    "Vlees",
    "Vis",
    "Huishouden",
    "Persoonlijke verzorging",
    "Baby",
    "Sportvoeding",
}

ALLOWED_TAGS = {
    "basis",
    "bonus",
    "actie",
    "vers",
    "gezond",
    "populair",
    "dagelijks",
    "budget",
    "eiwitrijk",
    "ontbijt",
    "houdbaar",
    "huishouden",
    "snack",
    "diepvries",
    "vlees",
    "vis",
    "zuivel",
}


class Product(BaseModel):
    id: int = Field(..., ge=1)
    name: str = Field(..., min_length=2)
    category: str = Field(..., min_length=2)
    prices: Dict[StoreId, float]
    tags: List[str] = Field(default_factory=list)
    substitute: Optional[str] = ""
    qualityScore: float = Field(..., ge=1, le=10)
    valueScore: float = Field(..., ge=1, le=10)
    brandType: Literal["mix", "huismerk", "voordeel"]
    reviewLabel: str = Field(..., min_length=10)
    lastUpdated: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name mag niet leeg zijn")
        return value

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        if value not in ALLOWED_CATEGORIES:
            raise ValueError(f"onbekende categorie: {value}")
        return value

    @field_validator("prices")
    @classmethod
    def validate_prices(cls, value: Dict[str, float]) -> Dict[str, float]:
        keys = set(value.keys())
        missing = REQUIRED_STORES - keys
        extra = keys - REQUIRED_STORES

        if missing:
            raise ValueError(f"missende winkelprijzen: {sorted(missing)}")
        if extra:
            raise ValueError(f"onbekende winkels: {sorted(extra)}")

        for store, price in value.items():
            if price <= 0:
                raise ValueError(f"prijs voor {store} moet groter zijn dan 0")
            if price > 100:
                raise ValueError(f"prijs voor {store} lijkt onrealistisch hoog: {price}")

        return {store: round(float(price), 2) for store, price in value.items()}

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: List[str]) -> List[str]:
        cleaned = []
        for tag in value:
            tag = str(tag).strip().lower()
            if tag not in ALLOWED_TAGS:
                raise ValueError(f"onbekende tag: {tag}")
            if tag not in cleaned:
                cleaned.append(tag)
        if not cleaned:
            raise ValueError("minimaal 1 tag vereist")
        if len(cleaned) > 6:
            raise ValueError("maximaal 6 tags toegestaan")
        return cleaned

    @field_validator("qualityScore", "valueScore")
    @classmethod
    def round_score(cls, value: float) -> float:
        return round(float(value), 1)

    @model_validator(mode="after")
    def validate_brand_matches_name(self):
        lower_name = self.name.lower()

        if "huismerk" in lower_name and self.brandType != "huismerk":
            raise ValueError("brandType moet 'huismerk' zijn als naam 'huismerk' bevat")

        if "voordeel" in lower_name and self.brandType != "voordeel":
            raise ValueError("brandType moet 'voordeel' zijn als naam 'voordeel' bevat")

        if "huismerk" not in lower_name and "voordeel" not in lower_name and self.brandType not in {"mix"}:
            raise ValueError("brandType moet 'mix' zijn als naam geen huismerk/voordeel bevat")

        return self
