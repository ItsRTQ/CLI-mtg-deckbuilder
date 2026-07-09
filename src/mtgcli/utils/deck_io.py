from typing import Any, Dict, List
from pathlib import Path


def load_deck_file(path: Any) -> Dict[str, Any]:
    """Load a deck from disk, accepting either a plain-text decklist (.txt) or a
    deck JSON file, and return the normalized shape from ``normalize_deck_input``.

    Lets verification commands (cards-batch, prices-batch, budget) run directly on
    a drafted ``.txt`` decklist before it has been converted with ``deck-write``.
    """
    from mtgcli.utils.json_io import read_json
    from mtgcli.utils.decklist_parser import parse_decklist_text

    p = Path(path)
    if p.suffix.lower() == ".txt":
        entries = parse_decklist_text(p.read_text(encoding="utf-8"))
        return {"commanders": [], "main_deck": entries, "metadata": {}}
    return normalize_deck_input(read_json(p))


def normalize_deck_input(raw_deck: Any) -> Dict[str, Any]:
    """
    Normalizes deck input to a standard internal shape.

    Accepts:
      - flat list:  [{name, quantity}, ...]
      - structured: {main_deck: [...], commander?: "...", commanders?: [...]}
      - structured: {cards: [...], ...}

    Returns:
      {
        "commanders": ["Name"] or [],
        "main_deck": [{name, quantity}, ...],
        "metadata": { ...extra keys... }
      }

    CLI flags always take precedence over file-embedded commander metadata.
    """
    if isinstance(raw_deck, list):
        return {"commanders": [], "main_deck": _normalize_entries(raw_deck), "metadata": {}}

    if not isinstance(raw_deck, dict):
        raise ValueError(f"Unsupported deck format: {type(raw_deck).__name__}")

    main_deck = raw_deck.get("main_deck") or raw_deck.get("cards")
    if main_deck is None:
        raise ValueError(
            "Deck JSON must be a list or a dict with a 'main_deck' (or 'cards') key."
        )

    if not isinstance(main_deck, list):
        raise ValueError("'main_deck' must be a list of card entries.")
    main_deck = _normalize_entries(main_deck)

    # Extract commander(s)
    commanders: List[str] = []
    raw_commanders = raw_deck.get("commanders")
    raw_commander = raw_deck.get("commander")
    if raw_commanders is not None:
        if isinstance(raw_commanders, list):
            commanders = [str(c) for c in raw_commanders]
        else:
            commanders = [str(raw_commanders)]
    elif raw_commander is not None:
        commanders = [str(raw_commander)]

    # Everything else goes into metadata
    skip = {"main_deck", "cards", "commander", "commanders"}
    metadata = {k: v for k, v in raw_deck.items() if k not in skip}

    return {"commanders": commanders, "main_deck": main_deck, "metadata": metadata}


def _normalize_entries(entries):
    """Accept card entries as plain strings OR {name, quantity} dicts — a deck JSON written by
    hand or by an agent naturally uses ["Sol Ring", ...]; every consumer downstream expects
    dicts. Normalizing HERE (the single load point) means no command can crash on the shape."""
    out = []
    for e in entries:
        if isinstance(e, str):
            out.append({"name": e, "quantity": 1})
        elif isinstance(e, dict):
            out.append(e)
        else:
            raise ValueError(f"Unsupported deck entry: {e!r} (expected string or object)")
    return out
