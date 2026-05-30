from typing import Dict, Any, List, Optional

BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}

_BUDGET_NOTES = {
    "under_budget": (
        "Budget is a maximum constraint, not a spending target. "
        "The deck does not need to use the full budget."
    ),
    "within_overage": (
        "Deck is above the requested budget but within the allowed overage."
    ),
    "over_budget": (
        "Deck exceeds the allowed overage and should be adjusted by replacing "
        "expensive low-synergy cards."
    ),
}


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


def evaluate_budget(
    known_price_total: float,
    budget_limit: float,
    overage_percent: float = 10.0,
) -> Dict[str, Any]:
    """
    Evaluates a known-price total against a budget limit.
    Returns status: under_budget, within_overage, or over_budget.
    Budget is a maximum constraint — under_budget is never a problem.
    """
    hard_budget = budget_limit * (1 + overage_percent / 100)

    if known_price_total <= budget_limit:
        status = "under_budget"
    elif known_price_total <= hard_budget:
        status = "within_overage"
    else:
        status = "over_budget"

    return {
        "budget_limit": round(budget_limit, 2),
        "allowed_overage_percent": overage_percent,
        "hard_budget_limit": round(hard_budget, 2),
        "budget_status": status,
        "note": _BUDGET_NOTES[status],
    }


def build_budget_summary(
    deck_entries: List[Dict[str, Any]],
    *,
    treat_basics_as_free: bool = True,
    budget_limit: Optional[float] = None,
    overage_percent: float = 10.0,
) -> Dict[str, Any]:
    """
    Summarizes USD budget for a list of card dicts (each may have quantity).
    Unknown-price cards are listed separately; they do NOT count as $0.

    If budget_limit is provided, evaluates the total against it and returns
    budget_status. Budget is a maximum constraint, not a spending target.
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

    result: Dict[str, Any] = {
        "known_price_total": round(known_total, 2),
        "currency": "USD",
        "known_price_cards_count": known_count,
        "unknown_price_cards_count": len(unknown_cards),
        "unknown_price_cards": unknown_cards,
        "budget_confidence": budget_confidence,
    }

    if budget_limit is not None:
        budget_eval = evaluate_budget(known_total, budget_limit, overage_percent)
        result.update(budget_eval)

    return result
