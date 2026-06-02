"""
Combo data parser.

Parses the raw JSON payload from the combo data source into clean combo objects.

Expected raw shape:
  raw["container"]["json_dict"]["cardlists"] -> list of cardlist entries

Each cardlist entry:
  entry["cardviews"]  -> list of card objects with "name"
  entry["combo"]      -> dict with "results" and optional "comboVote"
  entry["combo"]["comboVote"] -> dict with "bracket" (may be absent or null)
"""
from typing import Any, Dict, List, Optional


def _extract_bracket(combo_vote: Any) -> str:
    if isinstance(combo_vote, dict):
        bracket = combo_vote.get("bracket")
        return str(bracket) if bracket is not None else "N/A"
    return "N/A"


def parse_combos(raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse raw combo JSON into a list of clean combo dicts.

    Each combo dict:
      {
        "cards": ["Card A", "Card B"],
        "results": ["Infinite mana"],
        "bracket": "2"
      }

    Returns an empty list if the data is missing or malformed.
    """
    try:
        cardlists = (
            raw_data
            .get("container", {})
            .get("json_dict", {})
            .get("cardlists", [])
        )
    except (AttributeError, TypeError):
        return []

    combos = []
    for item in cardlists:
        if not isinstance(item, dict):
            continue

        cards = [
            card.get("name")
            for card in item.get("cardviews", [])
            if isinstance(card, dict) and card.get("name")
        ]
        if not cards:
            continue

        combo_data = item.get("combo") or {}
        results = combo_data.get("results") or []
        combo_vote = combo_data.get("comboVote")
        bracket = _extract_bracket(combo_vote)

        combos.append({
            "cards": cards,
            "results": results,
            "bracket": bracket,
        })

    return combos


def filter_combos(
    combos: List[Dict[str, Any]],
    bracket: Optional[str] = None,
    max_bracket: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Apply optional bracket and limit filters to parsed combos."""
    filtered = combos

    if bracket is not None:
        filtered = [c for c in filtered if c.get("bracket") == str(bracket)]

    if max_bracket is not None:
        def _numeric_bracket(b: str) -> float:
            try:
                return float(b)
            except (ValueError, TypeError):
                return float("inf")
        max_val = float(max_bracket)
        filtered = [c for c in filtered if _numeric_bracket(c.get("bracket", "N/A")) <= max_val]

    if limit is not None:
        filtered = filtered[:limit]

    return filtered


USE_GUIDANCE = {
    "mandatory_includes": False,
    "note": (
        "Combo data is recommendation/context data only. "
        "Cards must still pass legality, color identity, budget, power level, "
        "salt policy, and deck theme checks before inclusion."
    ),
}
