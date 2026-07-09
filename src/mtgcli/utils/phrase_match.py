"""Single source of truth for tag-phrase matching — the qualifier-interruption mechanism.

The tag vocabulary (data/seed/card_tags.json) is substring-based, which breaks whenever
oracle text interrupts a phrase with a qualifier: "another creature YOU OWN dies"
(Athreos), "gained 4 OR MORE life" (Angelic Accord — the first PRODUCTION sighting,
full build #3), "creature card WITH POWER LESS THAN X from your graveyard" (Mirko).
Five sightings were each patched with a measured literal variant; this module is the
GENERAL fix.

A phrase may contain the wildcard token ``" * "`` (space-star-space):

    "another creature * dies"

matches "another creature dies" AND "another creature you own dies". Semantics:
the gap spans at most ``QUALIFIER_GAP`` characters and never crosses a sentence or
line boundary (a qualifier is a short run inside ONE clause — an unbounded gap would
re-create the naked-substring false positives this project keeps killing).

Consumers (keep them ALL on this module — the multi-consumer drift lesson):
  - cards/search.py           SQL candidate retrieval (``to_like``) + rank counting
  - deckbuilder/deck_check.py role counting
  - deckbuilder/card_profile.py  function profiles (similar/complements/deck-gaps)
  - deckbuilder/suggestion_scorer.py  synergy scoring
  - deckbuilder/ramp_rules.py  the lands-as-ramp rule
  - cli/commands/deck.py      deck-gaps plan check

Phrases WITHOUT the token behave exactly as before (plain substring), so shipping
this module changes no behavior until a wildcard phrase enters the vocabulary.
"""
import re
from functools import lru_cache
from typing import List

# A qualifier is a short interruption inside one clause. 40 chars covers the measured
# sightings ("you own" 7, "4 or more" 9, "with power less than Mirko's power" 34)
# with margin, while staying far from free-text matching.
QUALIFIER_GAP = 40

_GAP_RE = r"[^.\n;]{0,%d}?" % QUALIFIER_GAP


@lru_cache(maxsize=4096)
def _compiled(phrase: str):
    parts = [re.escape(part.strip()) for part in phrase.lower().split(" * ") if part.strip()]
    if len(parts) < 2:
        return None  # degenerate wildcard use — treat as plain substring of the literal part
    return re.compile(_GAP_RE.join(parts))


def phrase_matches(phrase: str, text: str) -> bool:
    """True if `phrase` matches `text` (case-insensitive).

    Plain phrases: substring, byte-for-byte the pre-mechanism behavior.
    Wildcard phrases (" * "): literal parts in order, gaps bounded to one clause.
    """
    if not text:
        return False
    low = text.lower()
    if " * " not in phrase:
        return phrase.lower() in low
    rx = _compiled(phrase)
    if rx is None:
        return phrase.replace(" * ", " ").lower() in low
    return rx.search(low) is not None


def any_phrase_matches(phrases: List[str], text: str) -> bool:
    """Convenience for the common `any(p in text for p in phrases)` consumer shape."""
    return any(phrase_matches(p, text) for p in phrases)


def phrase_to_like(phrase: str) -> str:
    """SQL LIKE pattern for candidate retrieval: the wildcard maps to LIKE's ``%``.

    NOTE: LIKE's % is unbounded (it may cross clauses), so SQL retrieval is
    deliberately recall-oriented; every verdict-level consumer re-checks with
    `phrase_matches`, which enforces the bounded same-clause gap.
    """
    return "%" + phrase.lower().replace(" * ", "%") + "%"
