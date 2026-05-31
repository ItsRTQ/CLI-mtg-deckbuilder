"""
Commander analysis module.

Analyzes a commander card (and optional partner) to produce a structured JSON
artifact describing the commander's engine, synergy signals, archetype fit,
and deckbuilding pressures.

This is a heuristic analyzer — it uses oracle text and type line only.
It does not depend on AI memory, web access, or commander-specific templates.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from mtgcli.category_counts.scoring import (
    score_archetype_fit,
    score_commander,
    merge_partner_scores,
)


# ─── Type line parsing ────────────────────────────────────────────────────────

_ALL_SUPERTYPES = {"legendary", "basic", "snow", "world", "elite", "ongoing"}
_ALL_CARD_TYPES = {
    "creature", "artifact", "enchantment", "instant", "sorcery",
    "planeswalker", "land", "tribal", "battle", "dungeon", "background",
}


def _parse_type_line(type_line: str) -> Dict[str, List[str]]:
    parts = re.split(r"\s*[—–-]\s*", type_line, maxsplit=1)
    main_part = parts[0].strip().lower()
    sub_part = parts[1].strip() if len(parts) > 1 else ""
    words = main_part.split()
    supertypes = [w.capitalize() for w in words if w in _ALL_SUPERTYPES]
    card_types = [w.capitalize() for w in words if w in _ALL_CARD_TYPES]
    subtypes = [w.strip() for w in sub_part.split() if w.strip()] if sub_part else []
    return {"supertypes": supertypes, "card_types": card_types, "subtypes": subtypes}


# ─── Text signal extraction ───────────────────────────────────────────────────

_TRIGGER_PATTERNS = [
    "whenever", "when ", "at the beginning", "at end step",
    "the first time", "once each turn", "at the start of", "each time", "if ",
]
_ZONE_PATTERNS = [
    "graveyard", "exile", "hand", "library", "battlefield",
    "command zone", "top of your library",
]
_CARD_TYPE_PREF_PATTERNS = [
    "creature", "artifact", "enchantment", "instant", "sorcery",
    "land", "permanent", "noncreature", "nonland", "equipment", "aura", "token",
]
_PAYOFF_PATTERNS = [
    "draw", "damage", "drain", "gain life", "token", "mana",
    "return", "copy", "+1/+1", "counter", "destroy", "exile target",
]
_RESTRICTION_PATTERNS = [
    "once each turn", "only during your turn", "only as a sorcery",
    "nonland", "noncreature", "attacking", "combat damage", "nontoken", "another",
]
_ACTION_VERB_PATTERNS = [
    "draw", "discard", "sacrifice", "exile", "destroy", "counter",
    "create", "copy", "mill", "search", "return", "tap", "untap",
    "proliferate", "investigate", "discover", "adapt", "connive",
]


def _extract_text_signals(oracle: str) -> Dict[str, List[str]]:
    lower = oracle.lower()
    return {
        "trigger_conditions": [p for p in _TRIGGER_PATTERNS if p in lower],
        "resource_zones": [p for p in _ZONE_PATTERNS if p in lower],
        "preferred_card_types": [p for p in _CARD_TYPE_PREF_PATTERNS if p in lower],
        "scaling_axes": _extract_scaling(lower),
        "restrictions": [p for p in _RESTRICTION_PATTERNS if p in lower],
        "payoffs": [p for p in _PAYOFF_PATTERNS if p in lower],
        "action_verbs": [p for p in _ACTION_VERB_PATTERNS if p in lower],
    }


def _extract_scaling(oracle: str) -> List[str]:
    axes = []
    if "+1/+1 counter" in oracle or "proliferate" in oracle:
        axes.append("counters")
    if "token" in oracle and ("create" in oracle or "populate" in oracle):
        axes.append("tokens")
    if "whenever" in oracle and "damage" in oracle:
        axes.append("damage_triggers")
    if "whenever" in oracle and "draw" in oracle:
        axes.append("draw_triggers")
    if "graveyard" in oracle:
        axes.append("graveyard_count")
    if "each opponent" in oracle:
        axes.append("opponent_count")
    return axes


# ─── Engine pattern inference ─────────────────────────────────────────────────

# (pattern_name, signals, min_hits_required)
_ENGINE_RULES: List[Tuple[str, List[str], int]] = [
    ("etb_blink_engine", [
        "enters the battlefield", "exile", "return",
        "when this creature enters", "when it enters",
    ], 2),
    ("death_trigger_engine", [
        "whenever a creature dies", "when a creature dies",
        "whenever a creature you control dies",
        "creature dying", "a creature dying causes",
        "dies, ", "dies trigger",
    ], 1),
    ("sacrifice_value", [
        "sacrifice a creature", "sacrifice a permanent",
        "sacrifice an artifact", "sacrifice another",
    ], 1),
    ("token_engine", ["create", "token"], 2),
    ("spell_cast_engine", [
        "whenever you cast an instant", "whenever you cast a sorcery",
        "whenever you cast a spell", "magecraft",
    ], 1),
    ("landfall_landsmatter", [
        "landfall", "whenever a land enters", "whenever you play a land",
    ], 1),
    ("artifact_engine", [
        "whenever an artifact enters", "whenever you cast an artifact",
        "whenever an artifact you control",
    ], 1),
    ("enchantment_engine", [
        "constellation", "whenever an enchantment enters",
        "whenever you cast an enchantment",
    ], 1),
    ("equipment_aura_voltron", [
        "equipped creature", "enchanted creature",
        "whenever equipped", "bestow",
    ], 1),
    ("attack_trigger_engine", [
        "whenever this creature attacks", "whenever ~ attacks",
        "whenever you attack with",
    ], 1),
    ("combat_damage_engine", [
        "combat damage to a player", "combat damage to an opponent",
        "deals combat damage to",
    ], 1),
    ("lifegain_engine", [
        "whenever you gain life", "whenever a player gains life",
    ], 1),
    ("mill_engine", [
        "mill", "put cards from the top", "exile cards from the top",
    ], 1),
    ("graveyard_recursion", [
        "from your graveyard", "return to the battlefield from",
        "exile from a graveyard",
    ], 1),
    ("copy_engine", [
        "triggers an additional time", "creates a copy",
        "copy of target", "copies of",
    ], 1),
    ("counter_engine", ["+1/+1 counter", "proliferate", "-1/-1 counter"], 1),
    ("drain_engine", [
        "each opponent loses", "opponents lose life",
    ], 1),
    ("mana_engine", [
        "add {", "add mana of any type",
        "search your library for a basic land",
        "whenever a land or nonland permanent you control produces mana",
    ], 1),
]


def _infer_engine_patterns(oracle: str) -> List[str]:
    lower = oracle.lower()
    matched = []
    for pattern_name, signals, min_hits in _ENGINE_RULES:
        hits = sum(1 for s in signals if s in lower)
        if hits >= min_hits:
            matched.append((pattern_name, hits))
    matched.sort(key=lambda x: -x[1])
    return [name for name, _ in matched]


# ─── Commander type tags ──────────────────────────────────────────────────────

_COMMON_TRIBES = {
    "vampire", "zombie", "goblin", "dragon", "wizard", "elf",
    "human", "spirit", "dinosaur", "merfolk", "faerie", "demon",
    "angel", "knight", "warrior", "shaman", "cleric", "rogue",
    "artificer", "druid", "pirate", "horror", "beast", "elemental",
    "necron", "tyranid", "advisor", "assassin", "berserker", "bird",
    "cat", "centaur", "cyclops", "dwarf", "fish", "fox", "gnome",
    "golem", "hydra", "monk", "mutant", "naga", "ninja", "ogre",
    "plant", "rat", "shaman", "skeleton", "sliver", "soldier",
    "sphinx", "troll", "vedalken", "vampire",
}


def _build_commander_type_tags(card_types: List[str], subtypes: List[str]) -> List[str]:
    tags = []
    types_lower = [t.lower() for t in card_types]
    if "creature" in types_lower:
        tags.append("creature_commander")
    if "artifact" in types_lower:
        tags.append("artifact_commander")
    if "enchantment" in types_lower:
        tags.append("enchantment_commander")
    if "planeswalker" in types_lower:
        tags.append("planeswalker_commander")
    if "background" in types_lower:
        tags.append("background_commander")
    for subtype in subtypes:
        if subtype.lower() in _COMMON_TRIBES:
            tags.append(f"tribal_{subtype.lower()}")
    return tags


# ─── Synergy tags ─────────────────────────────────────────────────────────────

_ORACLE_TO_SYNERGY: List[Tuple[str, str]] = [
    ("graveyard", "graveyard"),
    ("exile", "exile_matters"),
    ("+1/+1 counter", "counters"),
    ("token", "tokens"),
    ("sacrifice", "sacrifice"),
    ("draw a card", "card_draw"),
    ("draws a card", "card_draw"),
    ("combat damage", "combat"),
    ("enters the battlefield", "etb"),
    ("landfall", "landfall"),
    ("constellation", "constellation"),
    ("equipment", "equipment"),
    ("aura", "aura"),
    ("gain life", "lifegain"),
    ("lifelink", "lifegain"),
    ("artifact", "artifact_matters"),
    ("enchantment", "enchantment_matters"),
    ("+1/+1", "counters"),
    ("proliferate", "proliferate"),
    ("whenever", "triggered_value"),
]


def _build_synergy_tags(engine_patterns: List[str], oracle: str) -> List[str]:
    tags: set = set(engine_patterns)
    lower = oracle.lower()
    for signal, tag in _ORACLE_TO_SYNERGY:
        if signal in lower:
            tags.add(tag)
    return sorted(tags)


# ─── Anti-synergy tags ────────────────────────────────────────────────────────

def _build_anti_synergy_tags(engine_patterns: List[str], oracle: str) -> List[str]:
    anti: set = set()
    if "etb_blink_engine" in engine_patterns:
        anti.add("non_permanent")
    if "spell_cast_engine" in engine_patterns:
        anti.add("permanent_heavy")
    if "mana_engine" in engine_patterns:
        anti.add("high_cost_generic")
    if "death_trigger_engine" in engine_patterns or "sacrifice_value" in engine_patterns:
        anti.add("graveyard_hate_effects")
    return sorted(anti)


# ─── Archetype fit ────────────────────────────────────────────────────────────

_ALL_ARCHETYPES = [
    "aristocrats", "artifacts", "auras", "battlecruiser", "blink", "combo",
    "control", "enchantress", "equipment", "go_tall_aggro", "go_wide_aggro",
    "graveyard_value", "group_slug", "landfall", "lands", "lifegain", "mill",
    "pillowfort", "reanimator", "spellslinger", "stax", "stompy", "theft",
    "tokens", "tribal", "value_engine", "voltron",
]

_ARCHETYPE_REASONS: Dict[str, str] = {
    "aristocrats": "Death triggers, sacrifice, or token production detected.",
    "blink": "Exile-and-return or ETB triggers detected.",
    "tokens": "Token creation or population detected.",
    "spellslinger": "Instant/sorcery cast triggers detected.",
    "artifacts": "Artifact synergy or triggers detected.",
    "enchantress": "Enchantment synergy or constellation detected.",
    "landfall": "Landfall or land-enters triggers detected.",
    "graveyard_value": "Graveyard interaction detected.",
    "reanimator": "Return from graveyard to battlefield detected.",
    "voltron": "Equipment/aura/modification synergy detected.",
    "equipment": "Equipment synergy detected.",
    "auras": "Aura/enchant creature synergy detected.",
    "lifegain": "Life gain triggers or lifelink detected.",
    "combo": "Untap, copy, or free-cast potential detected.",
    "control": "Counterspells or targeted removal detected.",
    "group_slug": "Each-opponent damage or drain detected.",
    "mill": "Mill or library-exile detected.",
    "tribal": "Creature subtype synergy detected.",
    "value_engine": "Draw or ETB value detected.",
    "counter_engine": "Counter placement or proliferate detected.",
}


def _compute_archetype_fit(
    oracle: str,
    type_line: str,
    forced_archetype: Optional[str] = None,
) -> List[Dict[str, Any]]:
    to_score = list(_ALL_ARCHETYPES)
    if forced_archetype and forced_archetype not in to_score:
        to_score.append(forced_archetype)

    fits = []
    for arch in to_score:
        score = score_archetype_fit(oracle, type_line, arch)
        if score >= 3.0:
            fits.append({
                "archetype": arch,
                "fit_score": round(score, 1),
                "reason": _ARCHETYPE_REASONS.get(arch, f"Text signals match {arch} patterns."),
            })
    fits.sort(key=lambda x: -x["fit_score"])
    return fits


# ─── Role pressures ───────────────────────────────────────────────────────────

def _pressure_label(score: float) -> str:
    if score <= 1.0:
        return "low"
    if score <= 3.5:
        return "normal"
    if score <= 6.0:
        return "medium"
    return "high"


def _compute_role_pressures(
    provides: Dict[str, float],
    requires: Dict[str, float],
    rewards: Dict[str, float],
    engine_patterns: List[str],
    best_archetype: str,
) -> Dict[str, str]:
    ramp = max(0.0, requires.get("normal_ramp", 2.0) - provides.get("normal_ramp", 0.0) * 0.5)
    prot = max(0.0, requires.get("protection", 2.0) - provides.get("protection", 0.0) * 0.5)
    draw = max(0.0, 2.5 - provides.get("draw", 0.0) * 0.5)
    arch_core = rewards.get("archetype_core", 2.0)
    syn_en = rewards.get("synergy_enablers", 2.0)
    syn_pay = rewards.get("synergy_payoffs", 2.0)

    if "etb_blink_engine" in engine_patterns:
        prot += 1.5
        arch_core += 2.0
    if "death_trigger_engine" in engine_patterns or "sacrifice_value" in engine_patterns:
        syn_en += 2.0
        syn_pay += 1.5
    if "combat_damage_engine" in engine_patterns or "attack_trigger_engine" in engine_patterns:
        prot += 2.0
    if "mana_engine" in engine_patterns:
        ramp -= 1.0

    board_wipes = best_archetype in ("control", "tokens", "aristocrats", "go_wide_aggro")
    counters = best_archetype == "control"

    return {
        "lands": "normal",
        "ramp": _pressure_label(ramp),
        "card_draw": _pressure_label(draw),
        "card_selection": "low",
        "removal": "normal",
        "board_wipes": "medium" if board_wipes else "low",
        "counterspells": "medium" if counters else "low",
        "protection": _pressure_label(prot),
        "recursion": "low",
        "graveyard_hate": "low",
        "tutors": "low",
        "win_conditions": "medium",
        "archetype_core": _pressure_label(arch_core),
        "synergy_enablers": _pressure_label(syn_en),
        "synergy_payoffs": _pressure_label(syn_pay),
        "redundancy": "normal",
        "utility": "normal",
    }


# ─── Wanted / Avoid patterns ──────────────────────────────────────────────────

def _build_wanted_patterns(
    engine_patterns: List[str],
    text_signals: Dict[str, List[str]],
    subtypes: List[str],
) -> List[str]:
    wanted: List[str] = []
    if "etb_blink_engine" in engine_patterns:
        wanted += ["ETB creatures", "blinkable permanents", "cheap ETB value"]
    if "death_trigger_engine" in engine_patterns:
        wanted += ["death trigger payoffs", "sacrifice outlets", "token generators"]
    if "sacrifice_value" in engine_patterns:
        wanted += ["sacrifice outlets", "death payoff creatures", "token makers"]
    if "token_engine" in engine_patterns:
        wanted += ["repeatable token makers", "token doublers", "anthem effects"]
    if "spell_cast_engine" in engine_patterns:
        wanted += ["cheap instants and sorceries", "spell payoffs", "cantrips"]
    if "mana_engine" in engine_patterns:
        wanted += ["mana doublers", "mana creatures", "nonland mana producers"]
    if "counter_engine" in engine_patterns:
        wanted += ["proliferate effects", "counter doublers", "counter payoffs"]
    if "combat_damage_engine" in engine_patterns or "attack_trigger_engine" in engine_patterns:
        wanted += ["evasion enablers", "unblockable effects", "protection equipment"]
    if "graveyard_recursion" in engine_patterns:
        wanted += ["self-mill enablers", "reanimation targets", "flashback spells"]
    if "landfall_landsmatter" in engine_patterns:
        wanted += ["extra land drops", "fetch lands", "landfall payoffs"]
    if "drain_engine" in engine_patterns:
        wanted += ["passive drain effects", "life loss triggers", "each-opponent effects"]
    if subtypes:
        tribal_targets = [s.lower() for s in subtypes[:2]]
        wanted.append(f"tribal synergy ({', '.join(tribal_targets)})")
    wanted += ["cheap mana rocks", "protection for commander"]
    return list(dict.fromkeys(wanted))


def _build_avoid_patterns(engine_patterns: List[str]) -> List[str]:
    avoid = [
        "high-cost generic goodstuff over engine pieces",
        "cards outside commander color identity",
    ]
    if "etb_blink_engine" in engine_patterns:
        avoid.append("non-permanent spells with low ETB value in blink deck")
    if "spell_cast_engine" in engine_patterns:
        avoid.append("permanent-heavy package when high spell count is needed")
    if "death_trigger_engine" in engine_patterns or "sacrifice_value" in engine_patterns:
        avoid.append("cards that exile graveyards (hurts own recursion)")
    if "mana_engine" in engine_patterns:
        avoid.append("high-cost cards that outpace ramp payoff timing")
    return avoid


# ─── Engine profile descriptions ─────────────────────────────────────────────

def _describe_engine_input(engine_patterns: List[str], requires: Dict[str, float]) -> str:
    parts = []
    if "etb_blink_engine" in engine_patterns:
        parts.append("permanents with ETB effects")
    if "death_trigger_engine" in engine_patterns or "sacrifice_value" in engine_patterns:
        parts.append("creatures to sacrifice or kill")
    if "spell_cast_engine" in engine_patterns:
        parts.append("cheap instants and sorceries")
    if "mana_engine" in engine_patterns:
        parts.append("mana producers and nonland permanents")
    if requires.get("protection", 0.0) > 1.5:
        parts.append("protection/evasion for commander")
    if requires.get("normal_ramp", 0.0) > 2.0:
        parts.append("early ramp to enable commander")
    return "; ".join(parts) or "Creatures, spells, and permanents matching color identity."


_ENGINE_ACTION_TEMPLATES: Dict[str, str] = {
    "etb_blink_engine": "{name} exiles and returns permanents, re-triggering ETB effects repeatedly.",
    "death_trigger_engine": "{name} creates value whenever creatures die.",
    "sacrifice_value": "{name} rewards or enables sacrificing permanents.",
    "token_engine": "{name} generates tokens to build a board state.",
    "spell_cast_engine": "{name} creates value whenever spells are cast.",
    "landfall_landsmatter": "{name} creates value whenever lands enter the battlefield.",
    "artifact_engine": "{name} synergizes with artifacts entering or activating.",
    "enchantment_engine": "{name} synergizes with enchantments entering.",
    "combat_damage_engine": "{name} creates value by dealing combat damage to players.",
    "attack_trigger_engine": "{name} triggers effects on each attack.",
    "counter_engine": "{name} places or benefits from +1/+1 counters.",
    "lifegain_engine": "{name} creates value from life gain triggers.",
    "graveyard_recursion": "{name} returns cards from graveyards to play.",
    "copy_engine": "{name} copies spells or triggers effects multiple times.",
    "drain_engine": "{name} drains opponents' life each turn.",
    "mana_engine": "{name} generates or amplifies mana production.",
}


def _describe_engine_action(primary_pattern: str, name: str) -> str:
    template = _ENGINE_ACTION_TEMPLATES.get(
        primary_pattern,
        "{name} generates value through its activated or triggered abilities.",
    )
    return template.format(name=name)


def _describe_engine_output(
    engine_patterns: List[str],
    provides: Dict[str, float],
    rewards: Dict[str, float],
) -> str:
    outputs = []
    if provides.get("draw", 0.0) > 0:
        outputs.append("card advantage")
    if provides.get("normal_ramp", 0.0) > 0:
        outputs.append("mana acceleration")
    if rewards.get("archetype_core", 0.0) > 1.5:
        outputs.append("archetype synergy value")
    if "token_engine" in engine_patterns:
        outputs.append("board presence via tokens")
    if "drain_engine" in engine_patterns:
        outputs.append("passive life drain")
    if "graveyard_recursion" in engine_patterns:
        outputs.append("card recursion")
    return "; ".join(outputs) or "Card advantage and board position."


_WIN_CONVERSION_MAP: Dict[str, str] = {
    "aristocrats": "Sacrifice loop drains opponents or generates enough damage through death triggers.",
    "blink": "Repeated ETB value outpaces opponents; combo finish with specific pieces.",
    "tokens": "Overrun with token army or drain effects from token count.",
    "combo": "Specific two-card combination generates infinite or decisive advantage.",
    "voltron": "Commander deals 21 commander damage to each opponent.",
    "control": "Counter and remove all threats; finish with remaining resources.",
    "landfall": "Landfall triggers overwhelm opponents with damage or board presence.",
    "mill": "Empty opponent libraries through mill effects.",
    "lifegain": "Near-infinite life buys time; kill via damage or combo.",
    "reanimator": "Cheat massive threats into play; win through card advantage.",
    "spellslinger": "Critical mass of spell triggers; combo finish or tempo advantage.",
    "enchantress": "Enchantment engine generates overwhelming card advantage.",
    "artifacts": "Artifact synergies generate mana/value; win through combo or combat.",
    "go_wide_aggro": "Token army wins through combat; use anthems or trample.",
    "value_engine": "Outvalue opponents through the commander engine; win via combat or attrition.",
}


def _describe_win_conversion(best_archetype: str, engine_patterns: List[str]) -> str:
    return _WIN_CONVERSION_MAP.get(
        best_archetype,
        "Outvalue opponents through the commander engine; win via combat or attrition.",
    )


# ─── Multiplayer scaling ──────────────────────────────────────────────────────

def _score_multiplayer_scaling(oracle: str) -> float:
    lower = oracle.lower()
    score = 3.0
    if "each opponent" in lower:
        score += 2.0
    if "all players" in lower or "each player" in lower:
        score += 1.5
    if "target player" in lower:
        score += 0.5
    if "triggers an additional time" in lower or "twice" in lower:
        score += 1.5
    return round(min(10.0, score), 2)


# ─── Build direction options ──────────────────────────────────────────────────

def _build_direction_options(
    archetype_fits: List[Dict[str, Any]],
    engine_patterns: List[str],
) -> List[str]:
    options = []
    if len(archetype_fits) >= 2:
        top = archetype_fits[0]["archetype"]
        second = archetype_fits[1]["archetype"]
        options.append(f"Primary: {top} build (highest natural fit)")
        options.append(f"Alternative: {second} hybrid approach")
    elif archetype_fits:
        options.append(f"Primary: {archetype_fits[0]['archetype']} build")
    if "counter_engine" in engine_patterns and "token_engine" in engine_patterns:
        options.append("Counter-token synergy hybrid")
    if "graveyard_recursion" in engine_patterns and "sacrifice_value" in engine_patterns:
        options.append("Aristocrats/recursion loop")
    return options


# ─── Main entry point ─────────────────────────────────────────────────────────

def analyze_commander(
    commander_card: Dict[str, Any],
    partner_card: Optional[Dict[str, Any]] = None,
    archetype: Optional[str] = None,
    theme: Optional[str] = None,
    power_level: Optional[float] = None,
    philosophy: Optional[str] = None,
    meta: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Produce a full commander analysis dict from card data.

    Uses oracle text and type line heuristics only — no AI memory or web access.
    """
    name = commander_card.get("name", "Unknown")
    can_be_cmd = commander_card.get("can_be_commander", False)
    is_cmd_legal = commander_card.get("commander_legal", False)
    type_line = commander_card.get("type_line", "")
    oracle = commander_card.get("oracle_text", "") or ""
    mana_cost = commander_card.get("mana_cost", "")
    mana_value = float(commander_card.get("mana_value") or 0)
    colors = sorted(commander_card.get("color_identity", []))
    power = commander_card.get("power")
    toughness = commander_card.get("toughness")
    keywords = commander_card.get("keywords", []) or []
    layout = commander_card.get("layout", "")

    is_valid = can_be_cmd

    parsed = _parse_type_line(type_line)
    supertypes = parsed["supertypes"]
    card_types = parsed["card_types"]
    subtypes = parsed["subtypes"]

    card_identity: Dict[str, Any] = {
        "name": name,
        "mana_cost": mana_cost,
        "mana_value": mana_value,
        "type_line": type_line,
        "card_types": card_types,
        "subtypes": subtypes,
        "supertypes": supertypes,
        "is_creature": "Creature" in card_types,
        "is_artifact": "Artifact" in card_types,
        "is_enchantment": "Enchantment" in card_types,
        "is_planeswalker": "Planeswalker" in card_types,
        "is_background": "Background" in card_types,
        "is_companion": "companion" in oracle.lower(),
        "power": power,
        "toughness": toughness,
        "keywords": keywords,
        "layout": layout,
    }

    text_signals = _extract_text_signals(oracle)
    engine_patterns = _infer_engine_patterns(oracle)
    primary_pattern = engine_patterns[0] if engine_patterns else "value_engine"
    secondary_patterns = engine_patterns[1:3]

    commander_type_tags = _build_commander_type_tags(card_types, subtypes)
    synergy_tags = _build_synergy_tags(engine_patterns, oracle)
    anti_synergy_tags = _build_anti_synergy_tags(engine_patterns, oracle)
    commander_tags = sorted(set(commander_type_tags + engine_patterns))

    archetype_fits = _compute_archetype_fit(oracle, type_line, archetype)
    best_archetype = archetype or (archetype_fits[0]["archetype"] if archetype_fits else "value_engine")

    forced_archetype_warning: Optional[str] = None
    if archetype:
        forced_score = next(
            (f["fit_score"] for f in archetype_fits if f["archetype"] == archetype), 1.0
        )
        if forced_score < 4.0:
            forced_archetype_warning = (
                f"This commander has a low fit score ({forced_score}) for {archetype}. "
                "Build is possible but not naturally supported by the commander text."
            )

    cmd_scores_raw = score_commander(commander_card, best_archetype)
    provides = cmd_scores_raw.get("provides", {})
    requires = cmd_scores_raw.get("requires", {})
    rewards = cmd_scores_raw.get("rewards", {})

    partner_name: Optional[str] = None
    partner_color_identity: List[str] = []
    partner_slots = 0

    if partner_card:
        partner_name = partner_card.get("name")
        partner_color_identity = partner_card.get("color_identity", [])
        partner_scores_raw = score_commander(partner_card, best_archetype)
        merged = merge_partner_scores(cmd_scores_raw, partner_scores_raw)
        cmd_scores_raw = merged
        provides = merged.get("provides", {})
        requires = merged.get("requires", {})
        rewards = merged.get("rewards", {})
        partner_slots = 1

    combined_color = sorted(set(colors + partner_color_identity))
    commander_slots = 1 + partner_slots
    library_slots = 99 - partner_slots

    multiplayer_scaling = _score_multiplayer_scaling(oracle)
    if partner_card:
        partner_oracle = (partner_card.get("oracle_text") or "").lower()
        multiplayer_scaling = max(multiplayer_scaling, _score_multiplayer_scaling(partner_oracle))

    commander_scores: Dict[str, float] = {
        "dependency": cmd_scores_raw.get("dependency", 5.0),
        "threat_reputation": cmd_scores_raw.get("threat_reputation", 4.0),
        "mana_value_pressure": cmd_scores_raw.get("mana_value_pressure", 0.0),
        "built_in_protection": cmd_scores_raw.get("built_in_protection", 0.0),
        "built_in_card_advantage": cmd_scores_raw.get("built_in_card_advantage", 0.0),
        "built_in_ramp": cmd_scores_raw.get("built_in_ramp", 0.0),
        "built_in_removal": cmd_scores_raw.get("built_in_removal", 0.0),
        "combo_potential": cmd_scores_raw.get("combo_potential", 0.0),
        "multiplayer_scaling": multiplayer_scaling,
    }

    role_pressures = _compute_role_pressures(
        provides, requires, rewards, engine_patterns, best_archetype
    )
    wanted = _build_wanted_patterns(engine_patterns, text_signals, subtypes)
    avoid = _build_avoid_patterns(engine_patterns)
    directions = _build_direction_options(archetype_fits, engine_patterns)

    notes: List[str] = []
    if power_level is not None:
        notes.append(f"Power level context: {power_level}/10")
    if philosophy:
        notes.append(f"Build philosophy: {philosophy}")
    if meta:
        notes.append(f"Meta context: {meta}")
    if theme:
        notes.append(f"Theme guidance: {theme}")
    if not can_be_cmd:
        notes.append("WARNING: Card may not be legal as a commander.")

    result: Dict[str, Any] = {
        "commander": name,
        "partner": partner_name,
        "is_valid_commander": is_valid,
        "commander_slots": commander_slots,
        "library_slots": library_slots,
        "color_identity": colors,
        "combined_color_identity": combined_color,
        "card_identity": card_identity,
        "text_signals": text_signals,
        "commander_tags": commander_tags,
        "commander_type_tags": commander_type_tags,
        "synergy_tags": synergy_tags,
        "anti_synergy_tags": anti_synergy_tags,
        "engine_profile": {
            "primary_pattern": primary_pattern,
            "secondary_patterns": secondary_patterns,
            "input": _describe_engine_input(engine_patterns, requires),
            "engine_action": _describe_engine_action(primary_pattern, name),
            "output": _describe_engine_output(engine_patterns, provides, rewards),
            "win_conversion": _describe_win_conversion(best_archetype, engine_patterns),
        },
        "archetype_fit": archetype_fits,
        "best_archetype": best_archetype,
        "role_pressures": role_pressures,
        "commander_scores": commander_scores,
        "provides": {k: round(v, 2) for k, v in provides.items()},
        "requires": {k: round(v, 2) for k, v in requires.items()},
        "rewards": {k: round(v, 2) for k, v in rewards.items()},
        "wanted_card_patterns": wanted,
        "avoid_card_patterns": avoid,
        "build_direction_options": directions,
        "notes": notes,
    }

    if forced_archetype_warning:
        result["forced_archetype_warning"] = forced_archetype_warning

    return result
