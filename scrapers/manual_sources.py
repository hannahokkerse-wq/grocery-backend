from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCES_DIR = BASE_DIR / "data" / "store_sources"


def load_store_source(filename: str):
    path = SOURCES_DIR / filename
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, dict):
        return payload.get("items", [])
    return payload


def load_ah():
    return load_store_source("ah.json")


def load_jumbo():
    return load_store_source("jumbo.json")


def load_lidl():
    return load_store_source("lidl.json")


def load_aldi():
    return load_store_source("aldi.json")


STORE_SOURCE_MAP = {
    "ah": load_ah,
    "jumbo": load_jumbo,
    "lidl": load_lidl,
    "aldi": load_aldi,
}
