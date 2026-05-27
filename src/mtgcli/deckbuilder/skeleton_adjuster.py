import json
from pathlib import Path

from mtgcli.config import SEED_DATA_DIR
from mtgcli.deckbuilder.constraints import DeckConstraints


FLEXIBLE_BUCKET = "synergy"


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
    base_skeleton: dict[str, int],
    constraints: DeckConstraints
) -> dict[str, int]:
    rules = _load_constraint_rules()
    adjusted = dict(base_skeleton)

    # Apply exact counts first
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
