from typing import List, Dict, Any

COLOR_TO_LAND = {
    "W": "Plains",
    "U": "Island",
    "B": "Swamp",
    "R": "Mountain",
    "G": "Forest",
}

# WUBRG priority order for remainder distribution
_WUBRG_ORDER = ["W", "U", "B", "R", "G"]


def calculate_land_distribution(color_identity: List[str], slots: int) -> Dict[str, int]:
    """
    Distributes `slots` basic land slots across the given colors in WUBRG order.
    Colorless/empty identity → Wastes.
    Remainder lands go to earlier colors in WUBRG order.
    """
    if slots <= 0:
        return {}

    colors = [c for c in _WUBRG_ORDER if c in color_identity]

    if not colors:
        return {"Wastes": slots}

    base = slots // len(colors)
    remainder = slots % len(colors)

    dist: Dict[str, int] = {}
    for i, color in enumerate(colors):
        qty = base + (1 if i < remainder else 0)
        if qty > 0:
            dist[COLOR_TO_LAND[color]] = qty

    return dist


def fill_deck_with_lands(
    deck_entries: List[Dict[str, Any]],
    color_identity: List[str],
    target_main_deck_size: int,
) -> Dict[str, Any]:
    """
    Fills a partial deck with basic lands to reach `target_main_deck_size`.

    Returns a result dict:
      - filled: True on success or no-op, False on error
      - lands_added: {land_name: qty}
      - updated_deck: new deck entries list (only present on success)
      - error: message if over target

    Does NOT remove cards. If deck is over target, returns an error.
    """
    current_size = sum(e.get("quantity", 1) for e in deck_entries)
    remaining = target_main_deck_size - current_size

    if remaining < 0:
        return {
            "filled": False,
            "error": (
                f"Deck already has {current_size} main deck cards; "
                f"target is {target_main_deck_size}. No lands added."
            ),
            "current_main_deck_size": current_size,
            "target_main_deck_size": target_main_deck_size,
        }

    if remaining == 0:
        return {
            "filled": True,
            "lands_added": {},
            "current_main_deck_size": current_size,
            "target_main_deck_size": target_main_deck_size,
            "remaining_slots": 0,
            "updated_deck": list(deck_entries),
            "note": "Deck is already at the target size. No lands were added.",
        }

    lands = calculate_land_distribution(color_identity, remaining)

    # Merge into a copy of deck_entries (update qty if land already present)
    updated = [dict(e) for e in deck_entries]
    for land_name, qty in lands.items():
        existing = next((e for e in updated if e.get("name") == land_name), None)
        if existing:
            existing["quantity"] = existing.get("quantity", 1) + qty
        else:
            updated.append({"name": land_name, "quantity": qty})

    return {
        "filled": True,
        "lands_added": lands,
        "current_main_deck_size": current_size,
        "target_main_deck_size": target_main_deck_size,
        "remaining_slots": remaining,
        "updated_deck": updated,
    }
