from typing import List, Dict, Any, Set


BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}


def validate_commander_deck(commander_name: str, deck_cards: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validates a Commander deck according to basic rules:
    - Exactly 100 cards total (including commander).
    - Commander must be present.
    - No non-basic duplicates.
    - All cards must be commander legal.
    - All cards must fit within the commander's color identity.
    """
    errors = []
    
    # 1. Check if commander exists in the provided list
    commander = next((c for c in deck_cards if c["name"].lower() == commander_name.lower()), None)
    if not commander:
        errors.append({
            "type": "commander_missing",
            "message": f"Commander '{commander_name}' not found in the deck list."
        })
        return {"valid": False, "errors": errors}

    # 2. Total card count (summing quantities)
    total_cards = sum(c.get("quantity", 1) for c in deck_cards)
    if total_cards != 100:
        errors.append({
            "type": "deck_size",
            "message": f"Deck must have exactly 100 cards, but found {total_cards}."
        })

    # 3. Non-basic duplicates and Legality/Color Identity
    commander_identity = set(commander.get("color_identity", []))
    seen_cards = set()
    
    for card in deck_cards:
        name = card.get("name")
        quantity = card.get("quantity", 1)
        
        # Singleton check
        if name not in BASIC_LANDS:
            if name in seen_cards or quantity > 1:
                errors.append({
                    "type": "singleton_violation",
                    "card": name,
                    "message": f"Multiple copies of non-basic card '{name}' found."
                })
        seen_cards.add(name)
        
        # Legality check
        if not card.get("commander_legal"):
            errors.append({
                "type": "legality",
                "card": name,
                "message": f"Card '{name}' is not legal in the Commander format."
            })
            
        # Color Identity check
        card_identity = set(card.get("color_identity", []))
        if not card_identity.issubset(commander_identity):
            errors.append({
                "type": "color_identity",
                "card": name,
                "message": f"Card color identity {sorted(list(card_identity))} is outside commander color identity {sorted(list(commander_identity))}."
            })

    return {
        "valid": len(errors) == 0,
        "errors": errors
    }
