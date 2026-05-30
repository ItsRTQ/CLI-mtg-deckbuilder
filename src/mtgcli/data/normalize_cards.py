from typing import Any, Dict, List, Optional


def parse_price(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
    
    if "Legendary Creature" in type_line:
        return True
    
    if "can be your commander" in oracle_text.lower():
        return True
    
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


def normalize_card(card: Dict[str, Any]) -> Dict[str, Any]:
    """Transforms a raw Scryfall card dict into our internal format."""
    raw_oracle_id = card.get("oracle_id")
    name = card.get("name", "")
    return {
        "oracle_id": raw_oracle_id if raw_oracle_id else f"name:{name.lower()}",
        "name": name,
        "mana_cost": card.get("mana_cost", ""),
        "mana_value": card.get("cmc", 0),
        "type_line": get_type_line(card),
        "oracle_text": get_oracle_text(card),
        "colors": card.get("colors", []),
        "color_identity": card.get("color_identity", []),
        "commander_legal": card.get("legalities", {}).get("commander") == "legal",
        "can_be_commander": can_be_commander(card),
        "usd_price": parse_price((card.get("prices") or {}).get("usd")),
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
