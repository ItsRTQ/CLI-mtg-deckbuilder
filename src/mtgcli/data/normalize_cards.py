from typing import Any, Dict, List


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


def normalize_card(card: Dict[str, Any]) -> Dict[str, Any]:
    """Transforms a raw Scryfall card dict into our internal format."""
    return {
        "scryfall_id": card.get("id"),
        "oracle_id": card.get("oracle_id"),
        "name": card.get("name"),
        "set_code": card.get("set"),
        "collector_number": card.get("collector_number"),
        "mana_cost": card.get("mana_cost", ""),
        "mana_value": card.get("cmc", 0),
        "type_line": get_type_line(card),
        "oracle_text": get_oracle_text(card),
        "colors": card.get("colors", []),
        "color_identity": card.get("color_identity", []),
        "commander_legal": card.get("legalities", {}).get("commander") == "legal",
        "can_be_commander": can_be_commander(card),
        "rarity": card.get("rarity"),
        "usd_price": card.get("prices", {}).get("usd"),
        "layout": card.get("layout"),
        "games": card.get("games", []),
        "digital": card.get("digital", False),
        "finishes": card.get("finishes", [])
    }
