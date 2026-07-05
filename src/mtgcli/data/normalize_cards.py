from typing import Any, Dict, List, Optional


def parse_price(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_pt(value: Any) -> Optional[str]:
    """Normalizes a power/toughness value, preserving the original Scryfall string.

    P/T can be non-numeric ('*', '1+*', '?', '∞'), so never convert to a number.
    Returns None for missing or empty values.
    """
    if value is None:
        return None
    value = str(value).strip()
    return value if value else None


def get_power_toughness(card: Dict[str, Any]) -> tuple:
    """Returns (power, toughness) preferring top-level values, falling back to faces.

    Top-level Scryfall values win when present. For multi-face cards that only
    store P/T per face, use the first face that has any P/T data.
    """
    power = normalize_pt(card.get("power"))
    toughness = normalize_pt(card.get("toughness"))
    if power is not None or toughness is not None:
        return power, toughness

    for face in card.get("card_faces", []) or []:
        fp = normalize_pt(face.get("power"))
        ft = normalize_pt(face.get("toughness"))
        if fp is not None or ft is not None:
            return fp, ft

    return None, None


def get_oracle_text(card: Dict[str, Any]) -> str:
    """Extracts oracle text, handling multi-faced cards."""
    if "oracle_text" in card:
        return card["oracle_text"]
    
    if "card_faces" in card:
        return "\n---\n".join(
            face.get("oracle_text", "") for face in card["card_faces"]
        )
    
    return ""


def get_type_line(card: Dict[str, Any]) -> str:
    """Extracts type line, handling multi-faced cards."""
    if "type_line" in card:
        return card["type_line"]
    
    if "card_faces" in card:
        return " // ".join(
            face.get("type_line", "") for face in card["card_faces"]
        )
    
    return ""


def can_be_commander(card: Dict[str, Any]) -> bool:
    """Determines if a card can be a commander."""
    type_line = get_type_line(card)
    oracle_text = get_oracle_text(card)

    # "Legendary" and "Creature" may be separated by other supertypes ("Legendary Enchantment
    # Creature" — Theros Gods; "Legendary Artifact Creature") so the contiguous substring
    # "Legendary Creature" misses 180+ legal commanders.
    if "Legendary" in type_line and "Creature" in type_line:
        return True

    if "can be your commander" in oracle_text.lower():
        return True

    # Curated allowlist for face commanders the heuristic can't detect (non-creature
    # commanders with no oracle signal, e.g. some Legendary Vehicles).
    try:
        from mtgcli.cards.repository import _commander_overrides
        if card.get("name") in _commander_overrides():
            return True
    except Exception:
        pass

    return False


def min_known_price(current: Optional[float], candidate: Optional[float]) -> Optional[float]:
    """Returns the lower of two prices, treating None as 'no data' not zero."""
    if candidate is None:
        return current
    if current is None:
        return candidate
    return min(current, candidate)


def _price_status(prices: Dict[str, Any]) -> str:
    fields = ["usd", "usd_foil", "usd_etched", "eur", "eur_foil", "tix"]
    return "known" if any(parse_price(prices.get(f)) is not None for f in fields) else "unknown"


# Scryfall objects that are never deck-playable cards: token printings (they SHADOW real
# card names — the M5 'Timeless Witness' bug: the eternalize TOKEN row resolved in exact-
# name lookup instead of the real card, reporting commander_legal=False for a legal card),
# emblems, art-series cards, and the Vanguard/Planechase/Archenemy non-deck objects.
# Excluding them at ingest keeps name lookups and search pools clean. Measured in the
# shipped DB: 4,020 rows, 88 of them shadowing a real card's name.
NONPLAYABLE_LAYOUTS = frozenset({
    "token", "double_faced_token", "emblem", "art_series", "vanguard", "scheme", "planar",
})


def normalize_card(card: Dict[str, Any]) -> Dict[str, Any]:
    """Transforms a raw Scryfall card dict into our internal format."""
    raw_oracle_id = card.get("oracle_id")
    name = card.get("name", "")
    power, toughness = get_power_toughness(card)
    return {
        "oracle_id": raw_oracle_id if raw_oracle_id else f"name:{name.lower()}",
        "name": name,
        "mana_cost": card.get("mana_cost", ""),
        "mana_value": card.get("cmc", 0),
        "type_line": get_type_line(card),
        "oracle_text": get_oracle_text(card),
        "power": power,
        "toughness": toughness,
        "colors": card.get("colors", []),
        "color_identity": card.get("color_identity", []),
        "commander_legal": card.get("legalities", {}).get("commander") == "legal",
        "can_be_commander": can_be_commander(card),
        "usd_price": parse_price((card.get("prices") or {}).get("usd")),
        "edhrec_rank": card.get("edhrec_rank"),
        "usd_foil_price": parse_price((card.get("prices") or {}).get("usd_foil")),
        "usd_etched_price": parse_price((card.get("prices") or {}).get("usd_etched")),
        "eur_price": parse_price((card.get("prices") or {}).get("eur")),
        "eur_foil_price": parse_price((card.get("prices") or {}).get("eur_foil")),
        "tix_price": parse_price((card.get("prices") or {}).get("tix")),
        "price_source": "scryfall",
        "price_status": _price_status(card.get("prices") or {}),
        "layout": card.get("layout"),
        "games": card.get("games", []),
        "digital": card.get("digital", False),
        "finishes": card.get("finishes", [])
    }
