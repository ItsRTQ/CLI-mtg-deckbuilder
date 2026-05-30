from typing import List, Dict, Any, Set, Optional
from mtgcli.cards.repository import CardRepository


BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}


def validate_commander_deck(
    commander_name: str,
    deck_entries: List[Dict[str, Any]],
    repo: CardRepository,
    *,
    partner_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validates a Commander deck.
    Supports single commander (99-card main deck) and partner commanders (98-card main deck).
    Both commanders must be present in the deck_entries list.
    """
    errors = []
    commander_slots = 2 if partner_name else 1
    expected_total = 100

    # 1. Hydrate commanders
    commanders = []
    commander_names_lower = set()

    for cname in ([commander_name, partner_name] if partner_name else [commander_name]):
        card = repo.get_card_by_exact_name(cname)
        if not card:
            errors.append({
                "type": "commander_not_found",
                "message": f"Commander '{cname}' not found in database.",
            })
        else:
            if not card.get("can_be_commander"):
                errors.append({
                    "type": "invalid_commander",
                    "message": f"Card '{card['name']}' cannot be a commander.",
                })
            commanders.append(card)
            commander_names_lower.add(card["name"].lower())

    if not commanders:
        return {"valid": False, "errors": errors, "commander_slots": commander_slots}

    # Combined color identity from all commanders
    combined_identity: Set[str] = set()
    for c in commanders:
        combined_identity.update(c.get("color_identity", []))

    # 2. Hydrate deck cards
    deck_cards = []
    commanders_found: Set[str] = set()

    for entry in deck_entries:
        name = entry.get("name")
        quantity = entry.get("quantity", 1)
        if not name:
            continue

        card_data = repo.get_card_by_exact_name(name)
        if not card_data:
            errors.append({
                "type": "card_not_found",
                "card": name,
                "message": f"Card '{name}' not found in database.",
            })
            continue

        card_data["quantity"] = quantity
        deck_cards.append(card_data)

        if card_data["name"].lower() in commander_names_lower:
            commanders_found.add(card_data["name"].lower())

    # Check all commanders are present in deck list
    for cname_lower in commander_names_lower:
        if cname_lower not in commanders_found:
            display = next((c["name"] for c in commanders if c["name"].lower() == cname_lower), cname_lower)
            errors.append({
                "type": "commander_missing",
                "message": f"Commander '{display}' not found in the deck list.",
            })

    # 3. Total card count
    total_cards = sum(c.get("quantity", 1) for c in deck_cards)
    if total_cards != expected_total:
        errors.append({
            "type": "deck_size",
            "message": f"Deck must have exactly {expected_total} cards, but found {total_cards}.",
        })

    # 4. Per-card checks (singleton, legality, color identity)
    seen_cards: Set[str] = set()

    for card in deck_cards:
        name = card.get("name")
        quantity = card.get("quantity", 1)
        card_identity = set(card.get("color_identity", []))

        if name not in BASIC_LANDS:
            if name in seen_cards or quantity > 1:
                errors.append({
                    "type": "singleton_violation",
                    "card": name,
                    "message": f"Multiple copies of non-basic card '{name}' found.",
                })
        seen_cards.add(name)

        if not card.get("commander_legal"):
            errors.append({
                "type": "legality",
                "card": name,
                "message": f"Card '{name}' is not legal in the Commander format.",
            })

        if not card_identity.issubset(combined_identity):
            errors.append({
                "type": "color_identity",
                "card": name,
                "message": (
                    f"Card color identity {sorted(card_identity)} is outside "
                    f"commander color identity {sorted(combined_identity)}."
                ),
            })

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "commander_slots": commander_slots,
        "combined_color_identity": sorted(combined_identity),
    }
