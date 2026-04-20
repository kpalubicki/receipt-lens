"""Receipt category detection based on store name and purchased items."""

from __future__ import annotations

_CATEGORIES: list[tuple[str, list[str]]] = [
    ("fuel", [
        "bp", "shell", "esso", "exxon", "chevron", "mobil", "texaco", "sunoco", "conoco",
        "marathon", "circle k", "speedway", "wawa", "kwiktrip", "gas", "petrol", "fuel",
        "station", "orlen", "lotos", "neste",
    ]),
    ("groceries", [
        "walmart", "kroger", "safeway", "aldi", "lidl", "biedronka", "lidl", "netto",
        "spar", "tesco", "carrefour", "trader joe", "whole foods", "costco",
        "supermarket", "grocery", "food mart", "spożywczy", "delikatesy",
        "milk", "bread", "cheese", "eggs", "butter", "flour", "rice", "pasta",
        "vegetables", "fruit", "meat", "chicken", "beef", "pork", "fish",
    ]),
    ("dining", [
        "mcdonald", "burger king", "kfc", "subway", "pizza", "starbucks", "dunkin",
        "chipotle", "wendys", "taco bell", "domino", "restaurant", "cafe", "bistro",
        "diner", "grill", "sushi", "kebab", "bar ", "pub ", "eatery", "pizzeria",
        "kawiarnia", "restauracja",
    ]),
    ("health", [
        "pharmacy", "walgreens", "cvs", "rite aid", "apteka", "rossmann", "vitamin",
        "supplement", "medicine", "drug", "health", "clinic", "dental", "hospital",
        "optician", "fitness", "gym",
    ]),
    ("entertainment", [
        "cinema", "movie", "netflix", "spotify", "steam", "playstation", "xbox",
        "bowling", "concert", "theatre", "theater", "museum", "zoo", "amusement",
        "sport", "game", "kino",
    ]),
    ("clothing", [
        "zara", "h&m", "primark", "reserved", "mango", "gap", "nike", "adidas",
        "fashion", "clothing", "apparel", "shoes", "boots", "jacket", "dress",
        "shirt", "jeans", "underwear",
    ]),
    ("electronics", [
        "best buy", "apple store", "mediamarkt", "saturn", "rtv euro agd",
        "electronics", "computer", "laptop", "phone", "tablet", "cable",
        "battery", "charger", "headphone",
    ]),
    ("transport", [
        "uber", "lyft", "bolt", "taxi", "train", "pkp", "intercity", "bus",
        "tram", "metro", "parking", "toll", "autobus", "bilet",
    ]),
]


def categorize_receipt(store_name: str | None, items: list[str]) -> str:
    """Return the most likely category for a receipt.

    Checks store name first, then item names. Returns 'other' when nothing matches.

    Args:
        store_name: Name of the store (may be None).
        items: List of purchased item names.

    Returns:
        Category string: groceries, dining, fuel, health, entertainment,
        clothing, electronics, transport, or other.
    """
    combined = " ".join(filter(None, [store_name or ""] + items)).lower()

    scores: dict[str, int] = {}
    for category, keywords in _CATEGORIES:
        for kw in keywords:
            if kw in combined:
                scores[category] = scores.get(category, 0) + 1

    if not scores:
        return "other"

    return max(scores, key=lambda c: scores[c])
