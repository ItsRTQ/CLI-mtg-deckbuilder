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
    Both commanders must be present in deck_entries.
    """
    errors = []
    warnings = []
    commander_slots = 2 if partner_name else 1
    expected_main_deck_size = 100 - commander_slots  # 99 or 98

    # 1. Hydrate commanders
    commanders = []
    commander_names_lower: Set[str] = set()

    for cname in ([commander_name, partner_name] if partner_name else [commander_name]):
        card = repo.get_card_by_exact_name(cname)
        if not card:
            errors.append({
                "type": "commander_not_found",
                "card": cname,
                "message": f"Commander '{cname}' not found in database.",
            })
        else:
            if not card.get("can_be_commander"):
                errors.append({
                    "type": "invalid_commander",
                    "card": card["name"],
                    "message": f"Card '{card['name']}' cannot be a commander.",
                })
            commanders.append(card)
            commander_names_lower.add(card["name"].lower())

    if not commanders:
        return {
            "valid": False,
            "commander": commander_name,
            "partner": partner_name,
            "commander_slots": commander_slots,
            "expected_main_deck_size": expected_main_deck_size,
            "actual_main_deck_size": 0,
            "total_cards_including_commanders": 0,
            "errors": errors,
            "warnings": warnings,
            "combined_color_identity": [],
        }

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
                "message": f"Card '{name}' not found in database. Possible hallucination or misspelling.",
            })
            continue

        card_data = dict(card_data)
        card_data["quantity"] = quantity
        deck_cards.append(card_data)

        if card_data["name"].lower() in commander_names_lower:
            commanders_found.add(card_data["name"].lower())

    # Check all commanders are present in deck list
    for cname_lower in commander_names_lower:
        if cname_lower not in commanders_found:
            display = next(
                (c["name"] for c in commanders if c["name"].lower() == cname_lower),
                cname_lower,
            )
            errors.append({
                "type": "commander_missing",
                "card": display,
                "message": f"Commander '{display}' not found in the deck list.",
            })

    # 3. Separate commander cards from main deck cards
    main_deck_cards = [c for c in deck_cards if c.get("name", "").lower() not in commander_names_lower]
    actual_main_deck_size = sum(c.get("quantity", 1) for c in main_deck_cards)
    commander_cards_in_deck = [c for c in deck_cards if c.get("name", "").lower() in commander_names_lower]
    actual_commander_count = len(commander_cards_in_deck)
    total_cards = actual_main_deck_size + actual_commander_count

    if actual_main_deck_size != expected_main_deck_size:
        label = "partner" if partner_name else "single"
        errors.append({
            "type": "invalid_deck_size",
            "expected_main_deck_size": expected_main_deck_size,
            "actual_main_deck_size": actual_main_deck_size,
            "message": (
                f"Main deck must contain exactly {expected_main_deck_size} cards "
                f"for a {label}-commander deck."
            ),
        })

    # 4. Per-card checks on main deck only
    seen_cards: Set[str] = set()

    for card in main_deck_cards:
        name = card.get("name")
        quantity = card.get("quantity", 1)
        card_identity = set(card.get("color_identity", []))

        # Singleton rule
        if name not in BASIC_LANDS:
            if name in seen_cards or quantity > 1:
                errors.append({
                    "type": "singleton_violation",
                    "card": name,
                    "quantity": quantity,
                    "message": f"Non-basic cards may only appear once in Commander.",
                })
        seen_cards.add(name)

        # Commander legality
        if not card.get("commander_legal"):
            errors.append({
                "type": "not_commander_legal",
                "card": name,
                "message": f"Card '{name}' is not legal in Commander.",
            })

        # Color identity
        if not card_identity.issubset(combined_identity):
            errors.append({
                "type": "color_identity_violation",
                "card": name,
                "card_color_identity": sorted(card_identity),
                "allowed_color_identity": sorted(combined_identity),
                "message": (
                    f"Card color identity {sorted(card_identity)} is outside "
                    f"commander color identity {sorted(combined_identity)}."
                ),
            })

    return {
        "valid": len(errors) == 0,
        "commander": commander_name,
        "partner": partner_name,
        "commander_slots": commander_slots,
        "expected_main_deck_size": expected_main_deck_size,
        "actual_main_deck_size": actual_main_deck_size,
        "total_cards_including_commanders": total_cards,
        "errors": errors,
        "warnings": warnings,
        "combined_color_identity": sorted(combined_identity),
    }
