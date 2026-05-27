from typing import List, Dict, Any, Set, Optional
from mtgcli.cards.repository import CardRepository


BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}


def validate_commander_deck(
    commander_name: str, 
    deck_entries: List[Dict[str, Any]], 
    repo: CardRepository
) -> Dict[str, Any]:
    """
    Validates a Commander deck according to basic rules.
    Hydrates card data from the repository by name.
    """
    errors = []
    
    # 1. Hydrate Commander
    commander = repo.get_card_by_exact_name(commander_name)
    if not commander:
        errors.append({
            "type": "commander_not_found",
            "message": f"Commander '{commander_name}' not found in database."
        })
        return {"valid": False, "errors": errors}
    
    if not commander.get("can_be_commander"):
        errors.append({
            "type": "invalid_commander",
            "message": f"Card '{commander['name']}' cannot be a commander."
        })

    # 2. Hydrate Deck Cards and check presence of commander in deck list
    deck_cards = []
    commander_present = False
    
    for entry in deck_entries:
        name = entry.get("name")
        quantity = entry.get("quantity", 1)
        
        if not name:
            continue
            
        card_data = repo.get_card_by_exact_match(
            name, 
            entry.get("set_code"), 
            entry.get("collector_number")
        )
        
        if not card_data:
            errors.append({
                "type": "card_not_found",
                "card": name,
                "message": f"Card '{name}' not found in database."
            })
            continue
            
        card_data["quantity"] = quantity
        deck_cards.append(card_data)
        
        if card_data["name"].lower() == commander["name"].lower():
            commander_present = True

    if not commander_present:
        errors.append({
            "type": "commander_missing",
            "message": f"Commander '{commander['name']}' not found in the deck list."
        })

    # 3. Total card count (summing quantities)
    total_cards = sum(c.get("quantity", 1) for c in deck_cards)
    if total_cards != 100:
        errors.append({
            "type": "deck_size",
            "message": f"Deck must have exactly 100 cards, but found {total_cards}."
        })

    # 4. Non-basic duplicates and Legality/Color Identity
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
