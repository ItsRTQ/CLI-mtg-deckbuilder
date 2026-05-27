import re
from dataclasses import dataclass, field


@dataclass
class DeckConstraints:
    exact_counts: dict[str, int] = field(default_factory=dict)
    minimum_counts: dict[str, int] = field(default_factory=dict)
    maximum_counts: dict[str, int] = field(default_factory=dict)
    preferences: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)


CATEGORY_ALIASES = {
    "lands": ["land", "lands"],
    "ramp": ["ramp"],
    "card_draw": ["draw", "card draw", "card advantage"],
    "removal": ["removal", "interaction"],
    "board_wipes": ["board wipe", "board wipes", "sweeper", "sweepers"],
    "creatures": ["creature", "creatures"],
    "win_conditions": ["wincon", "wincons", "win condition", "win conditions", "finisher", "finishers"],
}


def _add_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def parse_constraints_from_text(text: str) -> DeckConstraints:
    normalized = text.lower()
    constraints = DeckConstraints()

    for category, aliases in CATEGORY_ALIASES.items():
        for alias in aliases:
            # exact count: "33 lands", "12 ramp", "exactly 33 lands"
            exact_patterns = [
                rf"\bexactly\s+(\d+)\s+{re.escape(alias)}\b",
                rf"\b(\d+)\s+{re.escape(alias)}\b"
            ]

            for pattern in exact_patterns:
                match = re.search(pattern, normalized)
                if match:
                    constraints.exact_counts[category] = int(match.group(1))

            # minimum: "at least 30 creatures"
            min_pattern = rf"\bat least\s+(\d+)\s+{re.escape(alias)}\b"
            match = re.search(min_pattern, normalized)
            if match:
                constraints.minimum_counts[category] = int(match.group(1))

            # maximum: "no more than 3 board wipes"
            max_pattern = rf"\bno more than\s+(\d+)\s+{re.escape(alias)}\b"
            match = re.search(max_pattern, normalized)
            if match:
                constraints.maximum_counts[category] = int(match.group(1))

    preference_phrases = {
        "more ramp": "more_ramp",
        "less ramp": "less_ramp",
        "more draw": "more_card_draw",
        "more card draw": "more_card_draw",
        "less draw": "less_card_draw",
        "less card draw": "less_card_draw",
        "more removal": "more_removal",
        "less removal": "less_removal",
        "more creatures": "more_creatures",
        "more creature": "more_creatures",
        "fewer board wipes": "fewer_board_wipes",
        "less board wipes": "fewer_board_wipes",
        "more equipment": "more_equipment"
    }

    for phrase, preference in preference_phrases.items():
        if phrase in normalized:
            _add_unique(constraints.preferences, preference)

    avoid_phrases = {
        "no infinite combos": "infinite_combos",
        "avoid infinite combos": "infinite_combos",
        "no tutors": "tutors",
        "avoid tutors": "tutors"
    }

    for phrase, avoid in avoid_phrases.items():
        if phrase in normalized:
            _add_unique(constraints.avoid, avoid)

    return constraints
