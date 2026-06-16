"""Single source of truth for how lands relate to mana-ramp tags and the ramp role.

Several consumers need the exact same rule: a land may only be treated as ramp when
it actually ramps (fetches a land, plays an extra land, recurs a land) — never merely
because it taps for mana. Without a shared definition the consumers drift apart, which
is exactly how `deck-check` ended up counting every basic land as ramp (its reminder
text "({T}: Add {R}.)" matches the mana_rock phrase "{T}: Add") while `suggest` did not.

Consumers:
- suggestion_scorer.score_card_for_role  → filters matched tags for land cards
- deck_check.check_deck_quality          → decides if a land counts toward ramp stats
- cards.search.search_by_tags            → drops mana-leaked lands from tag searches
"""
from typing import Any, Dict, Iterable, List, Set


# Tags that produce mana but are NOT land-oriented. Their presence in a search or role
# means any land in scope must qualify through a land-oriented tag, not through these.
MANA_RAMP_TAGS = frozenset({
    "mana_rock", "mana_dork", "ritual", "treasure", "cost_reducer",
})

# The only tags through which a land may legitimately be treated as ramp.
RAMP_LAND_ALLOWED_TAGS = frozenset({
    "land_ramp", "extra_land_drop", "land_recursion",
})


def is_land(card: Dict[str, Any]) -> bool:
    return "land" in (card.get("type_line") or "").lower()


def _card_text(card: Dict[str, Any]) -> str:
    return (
        f"{card.get('name', '')} {card.get('type_line', '')} {card.get('oracle_text', '')}"
    ).lower()


def land_matches_allowed_ramp_tags(
    card: Dict[str, Any],
    tag_definitions: Dict[str, List[str]],
    allowed_tags: Iterable[str] = RAMP_LAND_ALLOWED_TAGS,
) -> bool:
    """True if a land matches at least one phrase from a land-oriented ramp tag.

    With the default ``allowed_tags`` this answers "does this land actually ramp?".
    Callers may pass a narrower set (e.g. only the land-ramp tags that were actually
    requested in a search) to scope the check.
    """
    text = _card_text(card)
    for tag in allowed_tags:
        for phrase in tag_definitions.get(tag, []):
            if phrase.lower() in text:
                return True
    return False


def resolve_tag_keys(
    tags: Iterable[str],
    tag_definitions: Dict[str, List[str]],
    role_definitions: Dict[str, Any],
) -> Set[str]:
    """Resolve requested tokens to the underlying card_tags keys they cover.

    Direct tag keys map to themselves; role names expand to their sub-tags; literal
    phrases (themes like 'goblins') contribute no keys. Mirrors the resolution used by
    ``_expand_tag_to_phrases`` but returns tag *keys* instead of phrases, so callers can
    reason about which categories a search actually touches.
    """
    keys: Set[str] = set()
    for tag in tags:
        if tag in tag_definitions:
            keys.add(tag)
        elif tag in role_definitions:
            keys.update(role_definitions[tag].get("tags", []))
    return keys
