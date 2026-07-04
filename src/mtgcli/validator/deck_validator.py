from typing import List, Dict, Any, Set, Optional
from mtgcli.cards.repository import CardRepository
from mtgcli.deckbuilder.land_filler import remove_command_zone_cards_from_main_deck


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

    Commander-zone cards live OUTSIDE the main deck. The commander does not
    need to appear inside ``deck_entries``; it is supplied via
    ``commander_name`` / ``partner_name`` (resolved from CLI flags or
    structured deck metadata by the caller).

    Supports single commander (99-card main deck) and partner commanders
    (98-card main deck). If a commander card is found inside the flat
    ``deck_entries`` list, it is treated as command-zone metadata, removed from
    the main-deck count, and reported in
    ``command_zone_cards_removed_from_main_deck`` (with a warning).
    """
    errors = []
    warnings = []
    commander_slots = 2 if partner_name else 1
    expected_main_deck_size = 100 - commander_slots  # 99 or 98

    commander_input_names = [commander_name] + ([partner_name] if partner_name else [])

    # 1. Hydrate commanders
    commanders = []
    commander_names_lower: Set[str] = set()

    for cname in commander_input_names:
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

    commander_display_names = [c["name"] for c in commanders]

    if not commanders:
        return {
            "valid": False,
            "commander": commander_name,
            "commanders": commander_display_names,
            "partner": partner_name,
            "commander_slots": commander_slots,
            "command_zone_cards_removed_from_main_deck": [],
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

    # 2. Strip any command-zone cards that leaked into the flat main-deck list.
    deck_entries, removed_from_main = remove_command_zone_cards_from_main_deck(
        deck_entries, commander_display_names
    )
    if removed_from_main:
        warnings.append({
            "type": "commander_in_main_deck",
            "cards": removed_from_main,
            "message": (
                "Commander-zone card(s) found in the flat deck list; treated as "
                "command-zone metadata and excluded from the main-deck count: "
                f"{', '.join(removed_from_main)}."
            ),
        })

    # 3. Hydrate main-deck cards (commanders already removed)
    main_deck_cards = []
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
        main_deck_cards.append(card_data)

    actual_main_deck_size = sum(c.get("quantity", 1) for c in main_deck_cards)
    total_cards = actual_main_deck_size + len(commanders)

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
                    f"'{name}' has color identity {sorted(card_identity)}, outside "
                    f"commander color identity {sorted(combined_identity)}."
                ),
            })

    return {
        "valid": len(errors) == 0,
        "commander": commander_name,
        "commanders": commander_display_names,
        "partner": partner_name,
        "commander_slots": commander_slots,
        "command_zone_cards_removed_from_main_deck": removed_from_main,
        "expected_main_deck_size": expected_main_deck_size,
        "actual_main_deck_size": actual_main_deck_size,
        "total_cards_including_commanders": total_cards,
        "errors": errors,
        "warnings": warnings,
        "combined_color_identity": sorted(combined_identity),
    }
