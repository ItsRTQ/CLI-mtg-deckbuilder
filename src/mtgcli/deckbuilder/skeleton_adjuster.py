import json
from pathlib import Path
from typing import Any, Optional

from mtgcli.config import SEED_DATA_DIR
from mtgcli.deckbuilder.constraints import DeckConstraints


FLEXIBLE_BUCKET = "synergy"
DECK_TOTAL = 100

# Fields that hold non-integer planning values and are resolved separately
_NON_INT_KEYS = {"description", "commander_slots"}


def get_main_deck_size(skeleton: dict) -> int:
    """Returns the number of non-commander slots for this skeleton (99 or 98)."""
    commander_slots = skeleton.get("commander_slots", 1)
    return DECK_TOTAL - commander_slots


def resolve_flexible_value(value: Any, constraint_override: Optional[int] = None) -> int:
    """Resolves a skeleton field value to an integer.

    - int: returned as-is
    - str formula (e.g. 'calculate_by_formula'): resolved to 35 default; agent overrides at build time
    - dict flexible_range: resolved to target; constraint_override wins if provided
    """
    if constraint_override is not None:
        return constraint_override

    if isinstance(value, int):
        return value

    if isinstance(value, dict) and value.get("mode") == "flexible_range":
        return value.get("target", value.get("min", 35))

    if isinstance(value, str):
        # String formulas are placeholders; return a sensible default for adjuster math
        return 35

    return 0


def get_flexible_land_range(skeleton: dict) -> Optional[dict]:
    """Returns the min/target/max range if skeleton uses flexible_range for lands, else None."""
    lands = skeleton.get("lands")
    if isinstance(lands, dict) and lands.get("mode") == "flexible_range":
        return {"min": lands["min"], "target": lands["target"], "max": lands["max"]}
    return None


def resolve_skeleton_to_int(
    skeleton: dict,
    land_override: Optional[int] = None,
) -> dict[str, int]:
    """
    Returns a copy of the skeleton with all non-commander_slots values resolved to integers.
    Formula-string land values are resolved to 35 unless land_override is given.
    flexible_range land values are resolved to target unless land_override is given.
    """
    resolved: dict[str, int] = {}
    for key, value in skeleton.items():
        if key == "description":
            continue
        if key == "commander_slots":
            resolved[key] = int(value)
        elif key == "lands":
            resolved[key] = resolve_flexible_value(value, land_override)
        else:
            resolved[key] = resolve_flexible_value(value)
    return resolved


def _load_constraint_rules() -> dict:
    path = SEED_DATA_DIR / "constraint_rules.json"
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _rebalance_to_100(skeleton: dict[str, int]) -> dict[str, int]:
    total = sum(skeleton.values())
    difference = 100 - total

    skeleton[FLEXIBLE_BUCKET] = skeleton.get(FLEXIBLE_BUCKET, 0) + difference

    if skeleton[FLEXIBLE_BUCKET] < 0:
        raise ValueError("Constraint adjustment made synergy count negative.")

    return skeleton


def apply_constraints_to_skeleton(
    base_skeleton: dict,
    constraints: DeckConstraints,
    land_override: Optional[int] = None,
) -> dict[str, int]:
    """
    Resolves any flexible/formula values in the skeleton, applies user constraints,
    rebalances to exactly 100, and returns the final integer skeleton.
    """
    rules = _load_constraint_rules()

    # Resolve flexible_range and formula strings to integers first
    # User land constraint hard-locks the land count
    effective_land_override = land_override or constraints.exact_counts.get("lands")
    adjusted = resolve_skeleton_to_int(base_skeleton, land_override=effective_land_override)

    # Apply exact counts
    for category, count in constraints.exact_counts.items():
        adjusted[category] = count

    # Apply minimum counts
    for category, minimum in constraints.minimum_counts.items():
        adjusted[category] = max(adjusted.get(category, 0), minimum)

    # Apply maximum counts
    for category, maximum in constraints.maximum_counts.items():
        adjusted[category] = min(adjusted.get(category, 0), maximum)

    # Apply preference adjustments
    for preference in constraints.preferences:
        changes = rules.get("preference_adjustments", {}).get(preference, {})
        for category, delta in changes.items():
            adjusted[category] = adjusted.get(category, 0) + delta

    # Apply safety minimums
    for category, minimum in rules.get("minimum_safety_counts", {}).items():
        if category in adjusted:
            adjusted[category] = max(adjusted[category], minimum)

    # Apply safety maximums
    for category, maximum in rules.get("maximum_safety_counts", {}).items():
        if category in adjusted:
            adjusted[category] = min(adjusted[category], maximum)

    adjusted = _rebalance_to_100(adjusted)

    if sum(adjusted.values()) != 100:
        raise ValueError(f"Adjusted skeleton must total 100, got {sum(adjusted.values())}")

    return adjusted


def normalize_deck_to_legal_size(
    slot_counts: dict[str, int],
    commander_slots: int = 1,
    land_range: Optional[dict] = None,
) -> dict[str, int]:
    """
    Trims or fills a slot count dict so the total equals exactly DECK_TOTAL.
    Trim priority (softest first): synergy, support, finishers, lands (within range).
    Fills from synergy if undersized.
    This prevents infinite builder/fixer loops for oversized skeletons.

    land_range: optional {"min": int, "target": int, "max": int}
    """
    target_total = DECK_TOTAL
    result = dict(slot_counts)
    land_min = land_range["min"] if land_range else 0

    current = sum(result.values())

    # Trim oversized deck
    trim_order = ["synergy", "support", "finishers", "win_conditions", "protection"]
    for bucket in trim_order:
        if current <= target_total:
            break
        available = result.get(bucket, 0)
        cut = min(available, current - target_total)
        result[bucket] = available - cut
        current -= cut

    # Trim lands last, respecting minimum
    if current > target_total and "lands" in result:
        over = current - target_total
        land_val = result["lands"]
        reducible = max(0, land_val - land_min)
        cut = min(reducible, over)
        result["lands"] = land_val - cut
        current -= cut

    # Fill undersized deck via synergy
    if current < target_total:
        result[FLEXIBLE_BUCKET] = result.get(FLEXIBLE_BUCKET, 0) + (target_total - current)

    return result
