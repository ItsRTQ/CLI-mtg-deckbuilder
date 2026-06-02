import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from mtgcli.config import SEED_DATA_DIR

_DEFAULT_ANALYSIS_PATH = Path("output/commander_analysis.json")

_RAMP_LAND_ALLOWED_TAGS = frozenset({"land_ramp", "extra_land_drop", "land_recursion"})

_SYNERGY_MECHANICS = [
    "sacrifice", "proliferate", "convoke", "delve", "explore", "adapt", "mutate",
    "foretell", "learn", "boast", "channel", "connive", "cultivate", "disturb",
    "enlist", "flash", "flashback", "fortify", "hideaway", "kicker", "morph",
    "ninjutsu", "overload", "partner", "persist", "populate", "raid", "revolt",
    "scry", "surge", "threshold", "transform", "undergrowth", "ward",
    "+1/+1 counter", "-1/-1 counter", "poison counter", "energy counter",
    "whenever a creature dies", "whenever you cast", "whenever you gain life",
    "whenever you draw", "enters the battlefield", "graveyard", "exile",
    "create", "token", "copy", "enchant", "attach", "equip", "aura",
    "tap", "untap", "combat damage", "trample", "flying", "haste",
    "triggered ability", "activated ability", "mana ability",
]


def extract_commander_synergy_signals(
    commander_card: Dict[str, Any],
    analysis_path: Optional[Path] = _DEFAULT_ANALYSIS_PATH,
) -> Set[str]:
    """
    Extract synergy keywords for the given commander.

    If analysis_path exists, uses analysis["synergy_tags"] + ["commander_type_tags"]
    + engine profile patterns for richer signal coverage.
    Falls back to heuristic oracle/type-line extraction if not available.
    """
    resolved_path = Path(analysis_path) if analysis_path else None
    if resolved_path and resolved_path.exists():
        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                analysis = json.load(f)
            signals: Set[str] = set()
            signals.update(analysis.get("synergy_tags", []))
            signals.update(analysis.get("commander_type_tags", []))
            engine = analysis.get("engine_profile", {})
            if engine.get("primary_pattern"):
                signals.add(engine["primary_pattern"])
            signals.update(engine.get("secondary_patterns", []))
            # Also add key oracle phrases from analysis text_signals
            for zone in analysis.get("text_signals", {}).get("resource_zones", []):
                signals.add(zone)
            return signals
        except Exception:
            pass  # Fall through to heuristic below

    # Heuristic fallback: extract from oracle text and type line directly
    signals = set()
    oracle = commander_card.get("oracle_text", "").lower()
    type_line = commander_card.get("type_line", "").lower()

    if "—" in type_line:
        subtypes_part = type_line.split("—", 1)[1]
        for word in re.split(r"\s+", subtypes_part.strip()):
            word = word.strip()
            if len(word) > 2:
                signals.add(word)

    for mechanic in _SYNERGY_MECHANICS:
        if mechanic in oracle:
            signals.add(mechanic)

    return signals


def check_card_synergy(card: Dict[str, Any], signals: Set[str]) -> List[str]:
    """Returns list of matched synergy signals between card text and commander signals."""
    card_text = (
        card.get("name", "") + " " +
        card.get("type_line", "") + " " +
        card.get("oracle_text", "")
    ).lower()
    return [s for s in signals if s in card_text]


def _load_tag_definitions() -> Dict[str, List[str]]:
    tag_file = SEED_DATA_DIR / "card_tags.json"
    if not tag_file.exists():
        return {}
    with open(tag_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_role_config(role: str) -> Dict[str, Any]:
    role_file = SEED_DATA_DIR / "role_definitions.json"
    if not role_file.exists():
        return {}
    with open(role_file, "r", encoding="utf-8") as f:
        return json.load(f).get(role, {})


def _is_land(card: Dict[str, Any]) -> bool:
    return "land" in (card.get("type_line") or "").lower()


def _match_sub_tags(
    card_text: str,
    sub_tags: List[str],
    tag_definitions: Dict[str, List[str]],
) -> List[str]:
    """Returns list of sub-tag names where at least one phrase matches card_text."""
    matched = []
    for sub_tag in sub_tags:
        phrases = tag_definitions.get(sub_tag, [])
        for phrase in phrases:
            if phrase.lower() in card_text:
                matched.append(sub_tag)
                break
    return matched


def score_suggestion(card: Dict[str, Any], role: str, theme: Optional[str] = None) -> Dict[str, Any]:
    """
    Scores a card for a given role using sub-tag matching from role_definitions.json.
    Returns score (1-10), matched_tags (sub-tag names), and reason_hint.
    """
    score = 0
    matched_tags: List[str] = []
    reasons: List[str] = []

    name = card.get("name", "").lower()
    type_line = card.get("type_line", "").lower()
    oracle_text = card.get("oracle_text", "").lower()
    mana_value = card.get("mana_value", 0) or 0
    is_commander_legal = card.get("commander_legal", False)

    card_text = name + " " + type_line + " " + oracle_text

    tag_definitions = _load_tag_definitions()
    role_config = _load_role_config(role)

    requires_tag_match: bool = role_config.get("requires_tag_match", False)
    role_sub_tags: List[str] = role_config.get("tags", [])

    # 1. Sub-tag matching — tracks tag names, not phrases
    if role_sub_tags:
        matched_tags = _match_sub_tags(card_text, role_sub_tags, tag_definitions)

    # Lands must not match mana-producing ramp tags (mana_rock, mana_dork, etc.)
    # Only land-specific ramp tags are valid for land cards.
    if role == "ramp" and _is_land(card):
        matched_tags = [t for t in matched_tags if t in _RAMP_LAND_ALLOWED_TAGS]

    if matched_tags:
        score += 3
        reasons.append(f"Matches {role}: {', '.join(matched_tags)}")

    # For strict roles (ramp): require at least one tag match
    if requires_tag_match and not matched_tags:
        return {
            "score": 0,
            "matched_tags": [],
            "reason_hint": f"No {role} tag matched (required for role)",
        }

    # 2. Theme matching (+3)
    if theme:
        theme_lower = theme.lower()
        theme_match = False

        if theme_lower == "goblins" and "goblin" in card_text:
            theme_match = True
        elif theme_lower == "zombies" and "zombie" in card_text:
            theme_match = True
        elif theme_lower == "equipment" and ("equipment" in type_line or "equip" in oracle_text):
            theme_match = True
        elif theme_lower == "auras" and "aura" in type_line:
            theme_match = True
        elif theme_lower == "counters" and "+1/+1 counter" in oracle_text:
            theme_match = True
        elif theme_lower == "artifacts" and ("artifact" in type_line or "artifact" in oracle_text):
            theme_match = True
        elif theme_lower == "tokens" and ("create" in oracle_text and "token" in oracle_text):
            theme_match = True
        elif theme_lower == "sacrifice" and "sacrifice" in oracle_text:
            theme_match = True
        elif theme_lower in card_text:
            theme_match = True

        if theme_match:
            score += 3
            reasons.append(f"Matches theme: {theme}")
            if theme_lower not in matched_tags:
                matched_tags.append(theme_lower)

    # 3. Role-specific efficiency logic
    if role == "ramp":
        # Efficiency bonus only when a ramp tag is already matched
        if matched_tags and mana_value <= 3:
            score += 2
            reasons.append("Efficient mana value bonus")

    elif role == "cheap":
        # cheap requires low mana value — filter out anything too expensive
        if mana_value <= 2:
            score += 3
            reasons.append("Low mana value (≤2)")
        elif mana_value <= 3:
            score += 2
            reasons.append("Low mana value (≤3)")
        else:
            return {
                "score": 0,
                "matched_tags": matched_tags,
                "reason_hint": f"Mana value {mana_value} too high for cheap role (max 3)",
            }

    elif role in ["removal", "card_draw", "protection"] and mana_value <= 3:
        score += 2
        reasons.append("Efficient mana value for role")

    # 4. Commander legality bonus (+1)
    if is_commander_legal:
        score += 1

    # 5. High cost penalty (-2)
    if mana_value >= 6 and role not in ["win_conditions", "finisher"]:
        score -= 2
        reasons.append("High mana value for utility role")

    # 6. Missing oracle text penalty (-3)
    if not oracle_text and "land" not in type_line:
        score -= 3
        reasons.append("Missing oracle text on non-land")

    final_score = max(1, min(10, score))
    reason_hint = "; ".join(reasons) if reasons else "Generic match"

    return {
        "score": final_score,
        "matched_tags": matched_tags,
        "reason_hint": reason_hint,
    }
