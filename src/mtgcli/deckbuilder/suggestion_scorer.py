import json
from typing import Dict, Any, List, Optional
from mtgcli.config import SEED_DATA_DIR

def score_suggestion(card: Dict[str, Any], role: str, theme: Optional[str] = None) -> Dict[str, Any]:
    """
    Heuristically scores a card based on its role and optional theme.
    Returns a score from 1-10, matched tags, and a reason hint.
    """
    score = 0
    matched_tags = []
    reasons = []

    name = card.get("name", "").lower()
    type_line = card.get("type_line", "").lower()
    oracle_text = card.get("oracle_text", "").lower()
    mana_value = card.get("mana_value", 0)
    is_commander_legal = card.get("commander_legal", False)

    # Load tag definitions for role matching
    tag_file = SEED_DATA_DIR / "card_tags.json"
    tag_definitions = {}
    if tag_file.exists():
        with open(tag_file, "r", encoding="utf-8") as f:
            tag_definitions = json.load(f)

    # 1. Role tag matching (+3)
    if role in tag_definitions:
        role_phrases = tag_definitions[role]
        matches_role = False
        for phrase in role_phrases:
            phrase_lower = phrase.lower()
            if phrase_lower in name or phrase_lower in type_line or phrase_lower in oracle_text:
                matches_role = True
                if phrase_lower not in matched_tags:
                    matched_tags.append(phrase_lower)
        
        if matches_role:
            score += 3
            reasons.append(f"Matches role: {role}")

    # 2. Theme matching (+3)
    if theme:
        theme_lower = theme.lower()
        theme_match = False
        
        # Specific theme logic
        if theme_lower == "goblins" and "goblin" in (name + type_line + oracle_text):
            theme_match = True
        elif theme_lower == "zombies" and "zombie" in (name + type_line + oracle_text):
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
        # Generic fallback
        elif theme_lower in (name + type_line + oracle_text):
            theme_match = True

        if theme_match:
            score += 3
            reasons.append(f"Matches theme: {theme}")
            if theme_lower not in matched_tags:
                matched_tags.append(theme_lower)

    # 3. Efficiency bonus (+2)
    # +2 if mana_value <= 3 for ramp, removal, card_draw, protection.
    if role in ["ramp", "removal", "card_draw", "protection"] and mana_value <= 3:
        score += 2
        reasons.append("Efficient mana value for role")

    # 4. Legality bonus (+1)
    if is_commander_legal:
        score += 1
    
    # 5. High cost penalty (-2)
    # -2 if mana_value >= 6 and role is not win_conditions.
    if mana_value >= 6 and role != "win_conditions":
        score -= 2
        reasons.append("High mana value for utility role")

    # 6. Oracle text penalty (-3)
    # -3 if card has no oracle_text and is not a land.
    if not oracle_text and "land" not in type_line:
        score -= 3
        reasons.append("Missing oracle text on non-land")

    # Final score processing
    final_score = max(1, min(10, score))
    reason_hint = "; ".join(reasons) if reasons else "Generic match"

    return {
        "score": final_score,
        "matched_tags": matched_tags,
        "reason_hint": reason_hint
    }
