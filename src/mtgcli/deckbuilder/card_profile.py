"""Shared card -> function profile: given a card, report which functions it performs.

This is the reverse of `search_by_tags` (which goes tag -> cards). It answers "what does THIS
card do?" by detecting which of the 97 functional tags its text satisfies, which trigger
families it has, and the generic oracle hooks (named counters, tokens, asymmetry, cost
reduction). It is the keystone reused by `similar` / `complements` (find related cards),
trigger-family search, and deck-gap analysis — built once so those features share one
definition of "function" instead of each re-deriving it (the anti-duplication rule).

Like everything functional here, detection is substring/heuristic and therefore imperfect; the
profile is a basis for proposing candidates, not a verdict.
"""
import json
from functools import lru_cache
from typing import Any, Dict, List, Optional

from mtgcli.config import SEED_DATA_DIR
from mtgcli.deckbuilder.oracle_hooks import extract_hooks, extract_trigger_events


@lru_cache(maxsize=1)
def _tag_definitions() -> Dict[str, List[str]]:
    path = SEED_DATA_DIR / "card_tags.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def matched_tags(card: Dict[str, Any], tag_definitions: Optional[Dict[str, List[str]]] = None) -> List[str]:
    """Return the functional tags whose phrases appear in the card's name/type/oracle text."""
    tags = tag_definitions if tag_definitions is not None else _tag_definitions()
    text = " ".join([
        card.get("name", "") or "",
        card.get("type_line", "") or "",
        card.get("oracle_text", "") or "",
    ]).lower()
    return [tag for tag, phrases in tags.items() if any(p.lower() in text for p in phrases)]


def card_function_profile(card: Dict[str, Any]) -> Dict[str, Any]:
    """Full functional profile of a single card: tags it satisfies, trigger families, and the
    generic oracle hooks. Used by similar/complements/trigger-search/deck-gaps."""
    oracle = card.get("oracle_text", "") or ""
    return {
        "name": card.get("name"),
        "tags": matched_tags(card),
        "trigger_events": extract_trigger_events(oracle),
        "hooks": extract_hooks(oracle),
    }


# Curated synergy map: a function -> the functions that PAY IT OFF or ENABLE it (the other half
# of the interaction). Keys and values are real card_tags.json tag names. Used by `complements`.
# Curated and partial by design; grows with use.
COMPLEMENT_MAP: Dict[str, List[str]] = {
    "sacrifice_outlet": ["death_trigger", "aristocrats", "reanimation", "graveyard_recursion", "token_maker"],
    "free_sacrifice_outlet": ["death_trigger", "aristocrats", "token_maker", "reanimation"],
    "mana_sacrifice_outlet": ["death_trigger", "aristocrats", "token_maker"],
    "death_trigger": ["sacrifice_outlet", "free_sacrifice_outlet", "token_maker", "repeatable_token_maker"],
    "aristocrats": ["sacrifice_outlet", "token_maker", "death_trigger"],
    "token_maker": ["go_wide_payoff", "anthem", "token_doubler", "sacrifice_outlet"],
    "repeatable_token_maker": ["go_wide_payoff", "anthem", "token_doubler", "sacrifice_outlet"],
    "go_wide_payoff": ["token_maker", "repeatable_token_maker", "anthem"],
    "counter_enabler": ["proliferate", "counter_payoff", "counter_doubler"],
    "counter_payoff": ["counter_enabler", "proliferate", "counter_doubler"],
    "proliferate": ["counter_enabler", "counter_payoff"],
    "self_mill": ["reanimation", "graveyard_recursion", "land_recursion"],
    "graveyard_recursion": ["self_mill", "sacrifice_outlet"],
    "reanimation": ["self_mill", "discard_outlet", "sacrifice_outlet"],
    "discard_outlet": ["reanimation", "graveyard_recursion"],
    "etb_value": ["blink"],
    "blink": ["etb_value"],
    "attack_trigger": ["evasion", "extra_combat", "go_wide_payoff", "haste"],
    "combat_damage_trigger": ["evasion", "double_strike", "extra_combat"],
    "evasion": ["damage_multiplier", "anthem", "double_strike"],
    "double_strike": ["buff", "anthem", "evasion"],
    "lifegain": ["lifegain_payoff"],
    "lifegain_payoff": ["lifegain", "lifedrain"],
    "spell_payoff": ["cheap_spell", "spell_copy", "card_draw", "ritual"],
    "magecraft": ["cheap_spell", "spell_copy", "card_draw"],
    "landfall": ["extra_land_drop", "land_ramp", "land_recursion"],
    "extra_land_drop": ["landfall", "land_ramp"],
    "treasure": ["sacrifice_outlet", "artifact_payoff", "spell_payoff"],
    "artifact_payoff": ["treasure", "artifact"],
    "enchantress": ["aura", "enchantment"],
    "aura": ["enchantress", "etb_value"],
}


def complementary_tags(profile_tags: List[str]) -> List[str]:
    """Given the tags a card satisfies, return the complementary tags (payoffs/enablers) to search
    for, deduped and excluding tags the source already has."""
    have = set(profile_tags)
    out: List[str] = []
    for t in profile_tags:
        for comp in COMPLEMENT_MAP.get(t, []):
            if comp not in have and comp not in out:
                out.append(comp)
    return out

