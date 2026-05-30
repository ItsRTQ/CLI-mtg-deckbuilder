from typing import Any, Dict, List


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
        return {"commanders": [], "main_deck": raw_deck, "metadata": {}}

    if not isinstance(raw_deck, dict):
        raise ValueError(f"Unsupported deck format: {type(raw_deck).__name__}")

    main_deck = raw_deck.get("main_deck") or raw_deck.get("cards")
    if main_deck is None:
        raise ValueError(
            "Deck JSON must be a list or a dict with a 'main_deck' (or 'cards') key."
        )

    if not isinstance(main_deck, list):
        raise ValueError("'main_deck' must be a list of card entries.")

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
