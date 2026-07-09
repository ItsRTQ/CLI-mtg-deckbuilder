"""General, commander-agnostic hook extraction from oracle text.

Instead of matching a commander against a fixed table of known archetypes (which is a
treadmill — every new commander mechanic needs a new hardcoded rule), this reads the
*structure* of the oracle text and pulls out generic features that work for ANY commander:

  - named counters        (slime / experience / +1/+1 / -1/-1 / oil / …)
  - token types created   (Slug / Drake / Saproling / Treasure / …)
  - trigger event families (dies / enters / targeted-by-spell / you-cast / attacks / sacrifice / …)
  - scaling references     ("for each X", "number of X")
  - asymmetry / punisher   (acts on "creatures you don't control" / "each opponent")
  - typed cost reduction   ("Hydra spells you cast cost {4} less")

From those features it derives `build_signals`: a generic shopping list. The mapping is from
generic features → signals (about a dozen rules), never from a specific commander name. This is
what lets the analyzer say useful things about a commander it has never seen.
"""
import re
from typing import Any, Dict, List, Set

# Counter TYPE noun: either a P/T form (+1/+1, -1/-1) or a word, immediately before "counter(s)".
# Negative lookahead drops the verb sense ("counter target spell", "counter that ability").
_COUNTER_RE = re.compile(
    r'([+\-]\d+/[+\-]\d+|[a-z][a-z\-]+) counters?\b(?! target| that| it| this| them| unless| spell| ability| a | the )',
    re.IGNORECASE,
)
# Words that precede "counter" but are not a counter TYPE.
_COUNTER_STOPWORDS = {
    "to", "the", "a", "an", "any", "that", "this", "those", "these", "more", "fewer",
    "one", "two", "three", "four", "many", "additional", "same", "such", "of", "or",
    "and", "another", "each", "no", "without", "with", "remove", "move",
}

_TOKEN_RE = re.compile(r'([A-Z][a-zA-Z]+) (?:creature )?tokens?\b')
_FOR_EACH_RE = re.compile(r'for each ([a-z][a-z\s\-/+\d]*?)(?:\.|,| you control| you don| that| on)', re.IGNORECASE)
_NUMBER_OF_RE = re.compile(r'number of ([a-z][a-z\s\-/+\d]*?)(?:\.|,| you| in| on| that)', re.IGNORECASE)
_COST_REDUCTION_RE = re.compile(r'([A-Z][a-zA-Z]+) spells (?:you cast )?cost \{?\d', re.IGNORECASE)

# Trigger clause → general event family. Checked against the trigger condition text only.
_TRIGGER_FAMILIES = [
    ("targeted_by_spell", ["becomes the target of a spell", "becomes the target of an ability", "becomes targeted"]),
    ("permanent_dies", ["dies", "put into a graveyard", "put into your graveyard", "leaves the battlefield", "is put into a graveyard"]),
    ("permanent_enters", ["enters"]),
    ("you_cast_spell", ["you cast"]),
    # "you attack" covers the player-scope form "whenever you attack" (Raffine, Adeline,
    # Inti — 156 cards measured), which the bare "attacks" keyword misses.
    # "you control attack" covers plural board subjects ("creatures/tokens you control
    # attack a player" — the batch #23 Neyali form).
    ("attacks_or_combat", ["attacks", "you attack", "you control attack", "deals combat damage", "blocks"]),
    ("sacrifice", ["sacrifice"]),
    ("draw_or_discard", ["draw", "discard"]),
    ("life_change", ["gain life", "lose life", "loses life", "gains life"]),
    ("recurring_tick", ["beginning of"]),
]


def _split_clauses(oracle: str) -> List[str]:
    parts: List[str] = []
    for line in (oracle or "").splitlines():
        parts.extend(s.strip() for s in line.split(".") if s.strip())
    return parts


def extract_named_counters(oracle: str) -> List[str]:
    out: List[str] = []
    for m in _COUNTER_RE.finditer(oracle or ""):
        kind = m.group(1).lower()
        if kind in _COUNTER_STOPWORDS:
            continue
        if kind not in out:
            out.append(kind)
    return out


def extract_token_types(oracle: str) -> List[str]:
    out: List[str] = []
    for m in _TOKEN_RE.finditer(oracle or ""):
        t = m.group(1)
        if t.lower() in {"creature", "artifact", "enchantment", "token"}:
            continue
        if t not in out:
            out.append(t)
    return out


# Ability words prefix a trigger as "Alliance — Whenever ..." / "Landfall — Whenever ...".
# The lookahead only strips when a real trigger condition follows the em dash, so flavor
# dashes and modal bullets are untouched. The M5 Galadriel build found the class: her
# Alliance trigger was invisible to trigger families — measured: 968 cards carry an
# ability-word-prefixed trigger (Landfall, Magecraft, Coven, Raid, Constellation, ...).
_ABILITY_WORD_PREFIX_RE = re.compile(
    r"^[a-z][a-z' ]{2,25}\s*—\s*(?=whenever |when |at the beginning)")


def extract_trigger_events(oracle: str) -> List[str]:
    events: List[str] = []
    for clause in _split_clauses(oracle):
        low = clause.lower()
        low = _ABILITY_WORD_PREFIX_RE.sub("", low)
        if not (low.startswith("whenever") or low.startswith("when") or low.startswith("at the beginning")):
            continue
        # Look only at the trigger condition (before the first comma) to classify.
        condition = low.split(",", 1)[0]
        for family, signals in _TRIGGER_FAMILIES:
            if any(sig in condition for sig in signals) and family not in events:
                events.append(family)
    return events


def has_activated_ability(oracle: str) -> bool:
    # Activated abilities are "<cost>: <effect>"; a colon mid-clause is the tell.
    for clause in _split_clauses(oracle):
        if ":" in clause and not clause.lower().startswith("choose"):
            return True
    return False


def extract_scaling(oracle: str) -> List[str]:
    out: List[str] = []
    for rx in (_FOR_EACH_RE, _NUMBER_OF_RE):
        for m in rx.finditer(oracle or ""):
            ref = m.group(1).strip()
            if ref and ref not in out:
                out.append(ref)
    return out


def is_asymmetric_punisher(oracle: str) -> bool:
    """True only for commanders that harm opponents' boards/resources in a MASS or recurring
    way — not for ones that merely have a single targeted fight/removal.

    The distinction is general, not commander-specific: "each opponent", "creatures your
    opponents control", or a plural / "each creature you don't control" all describe a one-sided
    board effect (Toxrill-style). A singular "target creature you don't control" is just targeted
    removal or a fight (Gargos-style) and must NOT register as a punisher, or the build gets
    steered toward attrition instead of its real game plan.
    """
    low = (oracle or "").lower()
    mass_signals = [
        "each opponent",
        "creatures your opponents control",
        "permanents your opponents control",
        "creatures you don't control",          # plural ⇒ mass board effect
        "permanents you don't control",
        "each creature you don't control",
        "all creatures you don't control",
        "creatures you don't control get",
    ]
    return any(s in low for s in mass_signals)


def extract_cost_reduction_type(oracle: str):
    m = _COST_REDUCTION_RE.search(oracle or "")
    return m.group(1) if m else None


_GENERIC_COUNTERS = {"+1/+1", "-1/-1"}


def derive_build_signals(hooks: Dict[str, Any]) -> List[str]:
    """Turn extracted features into a generic shopping list. Feature → signal, never
    commander → signal, so this fires for commanders the tool has never seen."""
    signals: List[str] = []
    counters = hooks["named_counters"]
    custom = [c for c in counters if c not in _GENERIC_COUNTERS]

    if "+1/+1" in counters:
        signals.append("+1/+1 counter payoffs, counter doublers, and proliferate")
    if "-1/-1" in counters:
        signals.append("-1/-1 counter / wither-style payoffs and proliferate")
    for c in custom:
        signals.append(
            f"proliferate to scale '{c}' counters; payoffs that count counters of ANY kind — "
            f"AVOID +1/+1-specific payoffs, which do nothing with '{c}' counters"
        )

    if hooks["asymmetric_punisher"]:
        signals.append(
            "one-sided/asymmetric effects and protection; win by attrition, not by going wide "
            "(your own board is not the payoff)"
        )

    fam = hooks["trigger_events"]
    if "targeted_by_spell" in fam:
        signals.append("cheap spells/auras that target your OWN creatures, and buyback auras (e.g. Whip Silk) to retrigger")
    if "permanent_dies" in fam:
        signals.append("sacrifice outlets, death-trigger payoffs, recursion, and cheap token fodder")
    if "permanent_enters" in fam:
        signals.append("value ETB creatures and blink/flicker effects")
    if "you_cast_spell" in fam:
        signals.append("low-cost instants/sorceries, spell copy, and cost reduction")
    if "attacks_or_combat" in fam:
        signals.append("evasion, extra combat steps, and combat-trigger payoffs")
    if "sacrifice" in fam:
        signals.append("cheap fodder, Treasure/Clue/token makers, and sacrifice payoffs")

    tokens = hooks["token_types"]
    if tokens and not hooks["asymmetric_punisher"]:
        signals.append(f"token doublers/anthems if {', '.join(tokens)} tokens come in multiples; otherwise treat them as sac fodder")

    if hooks["cost_reduction_type"]:
        t = hooks["cost_reduction_type"]
        signals.append(f"load up on {t} spells and {t} tribal payoffs (commander discounts them)")

    return signals


def extract_hooks(oracle_text: str) -> Dict[str, Any]:
    hooks: Dict[str, Any] = {
        "named_counters": extract_named_counters(oracle_text),
        "token_types": extract_token_types(oracle_text),
        "trigger_events": extract_trigger_events(oracle_text),
        "has_activated_ability": has_activated_ability(oracle_text),
        "scales_with": extract_scaling(oracle_text),
        "asymmetric_punisher": is_asymmetric_punisher(oracle_text),
        "cost_reduction_type": extract_cost_reduction_type(oracle_text),
    }
    hooks["build_signals"] = derive_build_signals(hooks)
    return hooks
