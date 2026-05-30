from typing import Dict, Any, List

BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}


def resolve_card_price(card: Dict[str, Any], preferred_currency: str = "usd") -> Dict[str, Any]:
    """Returns a resolved price dict for a single card in the preferred currency."""
    if preferred_currency == "usd":
        usd = card.get("usd_price")
        eur = card.get("eur_price")

        if usd is not None:
            return {
                "price": usd,
                "currency": "USD",
                "price_status": "known",
                "price_source": card.get("price_source", "scryfall"),
            }

        if eur is not None:
            return {
                "price": None,
                "currency": "USD",
                "price_status": "unknown_usd_known_eur",
                "eur_price": eur,
                "price_source": card.get("price_source", "scryfall"),
            }

        return {
            "price": None,
            "currency": "USD",
            "price_status": "unknown",
            "price_source": card.get("price_source", "scryfall"),
        }

    raise ValueError(f"Unsupported currency: {preferred_currency}")


def build_budget_summary(
    deck_entries: List[Dict[str, Any]],
    *,
    treat_basics_as_free: bool = True,
) -> Dict[str, Any]:
    """
    Summarizes USD budget for a list of card dicts (each may have quantity).
    Unknown-price cards are listed separately; they do NOT count as $0.
    """
    known_total = 0.0
    known_count = 0
    unknown_cards: List[str] = []

    for entry in deck_entries:
        name = entry.get("name", "")
        quantity = entry.get("quantity", 1)
        usd = entry.get("usd_price")

        if treat_basics_as_free and name in BASIC_LANDS:
            known_count += quantity
            continue

        if usd is not None:
            known_total += usd * quantity
            known_count += quantity
        else:
            unknown_cards.append(name)

    budget_confidence = "complete" if not unknown_cards else "partial"

    return {
        "known_price_total": round(known_total, 2),
        "currency": "USD",
        "known_price_cards_count": known_count,
        "unknown_price_cards_count": len(unknown_cards),
        "unknown_price_cards": unknown_cards,
        "budget_confidence": budget_confidence,
    }
