"""TCGplayer Mass Entry export.

Pure helpers: normalize a deck into purchase entries and build the Mass Entry URL
(https://www.tcgplayer.com/massentry?productline=Magic&c=||1 Sol Ring||...).
No I/O and no browser here — the CLI command and the GUI endpoint both build on these.
"""
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlencode

MASS_ENTRY_BASE = "https://www.tcgplayer.com/massentry"

# TCGplayer product titles keep BOTH halves only for split-style cards ("Wear //
# Tear", "Cut // Ribbons" — aftermath is layout `split` in this DB, listed here
# defensively). Every other multi-face layout (transform, modal_dfc, adventure,
# flip, prepare, reversible_card) is titled by its front face
# (TCGPLAYER_MASS_ENTRY_VERIFICATION.md §2.3).
_FULL_NAME_LAYOUTS = {"split", "aftermath"}


def normalize_deck_for_tcgplayer(
    deck_cards: List[Dict[str, Any]],
    commanders: Optional[List[str]] = None,
    layout_lookup: Optional[Callable[[str], Optional[str]]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Turns commander(s) + main deck into TCGplayer purchase entries.

    Commanders come first (quantity 1); a main-deck entry duplicating a commander is
    dropped (it is the same physical card). Multi-face names are matched to
    TCGplayer's catalog naming: split/aftermath keep the full "A // B" name, every
    other layout reduces to the front face. ``layout_lookup(name)`` supplies the
    layout (from the card DB); without it, "A // B" defaults to the front face.
    Entries with an empty name or a non-positive/non-integer quantity are skipped
    (returned in ``skipped``, never fatal). Duplicates merge by case-insensitive
    name, summing quantities, first-seen order preserved.

    Returns ``(cards, skipped)`` where cards are ``{"name", "quantity"}`` dicts.
    """
    merged: Dict[str, Dict[str, Any]] = {}  # lower-name -> {"name", "quantity"}
    skipped: List[Dict[str, Any]] = []

    def front_face(name: str) -> str:
        if " // " not in name:
            return name
        layout = layout_lookup(name) if layout_lookup else None
        if layout in _FULL_NAME_LAYOUTS:
            return name
        return name.split(" // ")[0]

    def add(name: Any, quantity: Any) -> None:
        clean = str(name).strip() if name is not None else ""
        if not clean:
            skipped.append({"name": name, "quantity": quantity})
            return
        try:
            qty = int(quantity)
        except (TypeError, ValueError):
            skipped.append({"name": clean, "quantity": quantity})
            return
        if qty < 1:
            skipped.append({"name": clean, "quantity": quantity})
            return
        clean = front_face(clean)
        key = clean.lower()
        if key in merged:
            merged[key]["quantity"] += qty
        else:
            merged[key] = {"name": clean, "quantity": qty}

    commander_keys = set()
    for name in commanders or []:
        add(name, 1)
        clean = str(name).strip() if name is not None else ""
        if clean:
            commander_keys.add(front_face(clean).lower())

    for card in deck_cards:
        name = card.get("name")
        clean = str(name).strip() if name is not None else ""
        if clean and front_face(clean).lower() in commander_keys:
            continue  # same physical card as the commander
        add(name, card.get("quantity", 1))

    return list(merged.values()), skipped


def build_tcgplayer_entries(cards: List[Dict[str, Any]]) -> List[str]:
    """Formats normalized cards as Mass Entry lines: '1 Sol Ring'."""
    return [f"{card['quantity']} {card['name']}" for card in cards]


def build_tcgplayer_mass_entry_url(cards: List[Dict[str, Any]]) -> str:
    """Builds the Mass Entry URL. The payload keeps its leading '||' and the whole
    query is encoded in a single urlencode pass (no per-name pre-encoding)."""
    payload = "||" + "||".join(build_tcgplayer_entries(cards))
    query = urlencode({"productline": "Magic", "c": payload})
    return f"{MASS_ENTRY_BASE}?{query}"
