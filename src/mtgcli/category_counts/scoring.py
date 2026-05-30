"""
Commander scoring heuristics.

All scores are floats 0-10 before clamping. These are heuristics derived from
oracle text and type line — not ground truth. The AI agent may override or
adjust these based on deeper commander analysis.
"""
from typing import Dict, Any, Optional
from .models import MV_PRESSURE_TABLE, MV_PRESSURE_HIGH

# ─── Archetype fit keyword patterns ───────────────────────────────────────────

_ARCHETYPE_FIT_KEYWORDS: Dict[str, list] = {
    "aristocrats": [
        "dies", "dying", "death", "sacrifice", "whenever a creature you control",
        "leaves the battlefield", "trigger", "triggered ability", "token", "lifelink",
    ],
    "voltron": [
        "equipment", "aura", "attach", "+1/+1 counter", "equipped creature",
        "enchanted creature", "modified",
    ],
    "tokens": [
        "create", "token", "amass", "populate", "manifest",
        "whenever a token",
    ],
    "spellslinger": [
        "instant or sorcery", "whenever you cast", "magecraft", "prowess",
        "spell you control", "instant", "sorcery",
    ],
    "control": [
        "counter target", "destroy target", "exile target",
        "end step", "draw a card", "until end of turn",
    ],
    "combo": [
        "each time", "untap", "additional", "you may cast", "copy",
        "free", "whenever", "each turn",
    ],
    "stompy": [
        "power is", "gets +", "trample", "fight", "ferocious",
        "+x/+x",
    ],
    "reanimator": [
        "from your graveyard", "return to the battlefield from",
        "graveyard", "dies", "exile from a graveyard",
    ],
    "graveyard_value": [
        "graveyard", "dies", "discard", "mill", "exile from a graveyard",
    ],
    "artifacts": [
        "artifact", "fabricate", "modular", "whenever an artifact",
        "whenever you cast an artifact",
    ],
    "enchantress": [
        "enchantment", "whenever an enchantment", "constellation",
        "enchanted", "whenever you cast an enchantment",
    ],
    "equipment": [
        "equipment", "equip", "equipped",
    ],
    "auras": [
        "aura", "enchant ", "enchanted creature",
    ],
    "lands": [
        "land", "landfall", "whenever a land",
        "search your library for a", "land card",
    ],
    "landfall": [
        "landfall", "whenever a land enters",
    ],
    "lifegain": [
        "gain life", "lifelink", "whenever you gain life", "life total",
        "whenever a player gains life",
    ],
    "group_slug": [
        "each opponent", "each player", "each other player",
        "deals damage to", "opponent loses life",
    ],
    "mill": [
        "mill", "put cards from", "top of their library",
        "exile cards from the top",
    ],
    "blink": [
        "exile target creature", "return it", "return that card",
        "enters the battlefield under your control",
        "when it enters the battlefield",
    ],
    "theft": [
        "gain control", "control of target",
    ],
    "go_wide_aggro": [
        "create", "token", "whenever a creature attacks",
        "attack with", "wide",
    ],
    "go_tall_aggro": [
        "+1/+1", "first strike", "double strike",
        "trample", "attack", "combat damage",
    ],
    "tribal": [
        "of the chosen type", "creature type",
        "whenever a creature you control of",
        "kindred", "lord",
    ],
    "pillowfort": [
        "can't attack you", "can't target you",
        "damage to you", "protection from",
        "prevent that damage",
    ],
    "stax": [
        "can't", "don't untap", "costs {", "costs more",
        "each opponent can't", "tax",
    ],
    "value_engine": [
        "draw", "whenever", "enters the battlefield",
        "put a card", "scry",
    ],
    "battlecruiser": [
        "mana value", "enters the battlefield",
        "trample", "power",
    ],
}


def score_archetype_fit(
    oracle_text: str,
    type_line: str,
    archetype: str,
) -> float:
    """Return 0-10 fit score for the commander/archetype combination."""
    if archetype not in _ARCHETYPE_FIT_KEYWORDS:
        return 5.0
    keywords = _ARCHETYPE_FIT_KEYWORDS[archetype]
    text = (oracle_text or "").lower() + " " + (type_line or "").lower()
    matches = sum(1 for kw in keywords if kw.lower() in text)
    if not keywords:
        return 5.0
    ratio = matches / len(keywords)
    # 0 matches → 1.0, all match → 10.0
    score = 1.0 + ratio * 9.0
    return min(10.0, score)


# ─── Commander provides (reduces category need) ───────────────────────────────

def _score_provides(oracle: str) -> Dict[str, float]:
    """Estimate how much the commander provides each category intrinsically."""
    provides: Dict[str, float] = {}

    # Draw
    draw_strength = 0.0
    if "draw a card" in oracle or "draws a card" in oracle:
        draw_strength += 2.0
    if "draw cards" in oracle or "draws cards" in oracle:
        draw_strength += 1.5
    if "look at the top" in oracle and "put" in oracle and "hand" in oracle:
        draw_strength += 1.0
    if "put" in oracle and "card" in oracle and "hand" in oracle:
        draw_strength += 0.5
    if draw_strength:
        provides["draw"] = min(5.0, draw_strength)

    # Ramp
    ramp_strength = 0.0
    if "add {" in oracle or "add mana" in oracle:
        ramp_strength += 2.5
    if "search your library for a" in oracle and "land" in oracle:
        ramp_strength += 2.0
    if "treasure" in oracle and ("create" in oracle or "add" in oracle):
        ramp_strength += 1.5
    if ramp_strength:
        provides["normal_ramp"] = min(5.0, ramp_strength)

    # Targeted removal
    removal_strength = 0.0
    if "destroy target" in oracle:
        removal_strength += 2.0
    if "exile target" in oracle:
        removal_strength += 2.0
    if "deal" in oracle and "damage to target" in oracle:
        removal_strength += 1.5
    if "-x/-x" in oracle or "-1/-1 counter" in oracle:
        removal_strength += 1.0
    if removal_strength:
        provides["targeted_removal"] = min(5.0, removal_strength)

    # Tutors
    if "search your library for a card" in oracle:
        provides["tutors"] = 3.0
    elif "search your library for" in oracle:
        provides["tutors"] = 1.5

    # Protection
    prot_strength = 0.0
    if "hexproof" in oracle:
        prot_strength += 2.5
    if "indestructible" in oracle:
        prot_strength += 2.5
    if "protection from" in oracle:
        prot_strength += 2.0
    if "shroud" in oracle:
        prot_strength += 2.0
    if prot_strength:
        provides["protection"] = min(5.0, prot_strength)

    # Board wipes
    if "destroy all" in oracle or "exile all" in oracle:
        provides["board_wipes"] = 2.5
    elif "each creature" in oracle and ("deals damage" in oracle or "loses" in oracle):
        provides["board_wipes"] = 1.0

    return provides


# ─── Commander requires (increases category need) ─────────────────────────────

def _score_requires(oracle: str, mv: float) -> Dict[str, float]:
    requires: Dict[str, float] = {}

    # Expensive commanders need ramp.
    if mv >= 3:
        requires["normal_ramp"] = max(0.0, (mv - 3.0) * 0.75)

    # Commanders that need to attack need protection.
    attack_need = 0.0
    if "whenever ~ attacks" in oracle or "whenever this creature attacks" in oracle:
        attack_need += 1.5
    if "whenever ~ deals combat damage" in oracle or "whenever this creature deals combat damage" in oracle:
        attack_need += 1.5
    if attack_need:
        requires["protection"] = attack_need

    # Tap-to-activate commanders need to stay on board.
    if "{t}:" in oracle.lower() or "tap this creature" in oracle:
        requires["protection"] = requires.get("protection", 0.0) + 0.5

    return requires


# ─── Commander rewards (deck cards make commander better) ─────────────────────

def _score_rewards(oracle: str, type_line: str, archetype: str) -> Dict[str, float]:
    rewards: Dict[str, float] = {}

    # Death-trigger rewards sacrifice/death engine.
    if "whenever a creature dies" in oracle or "when a creature dies" in oracle:
        rewards["archetype_core"] = rewards.get("archetype_core", 0.0) + 2.5
        rewards["synergy_enablers"] = rewards.get("synergy_enablers", 0.0) + 1.5

    # Sacrifice payoff.
    if "sacrifice a creature" in oracle or "sacrifice another creature" in oracle:
        rewards["synergy_enablers"] = rewards.get("synergy_enablers", 0.0) + 2.0

    # Spellslinger rewards instant/sorcery.
    if "whenever you cast" in oracle and (
        "instant" in oracle or "sorcery" in oracle or "spell" in oracle
    ):
        rewards["archetype_core"] = rewards.get("archetype_core", 0.0) + 2.5

    # ETB blink rewards blink/ETB shell.
    if (
        "when ~ enters the battlefield" in oracle
        or "whenever ~ enters the battlefield" in oracle
        or "when this creature enters the battlefield" in oracle
    ):
        rewards["synergy_enablers"] = rewards.get("synergy_enablers", 0.0) + 2.0

    # Combat-based rewards.
    if "whenever ~ attacks" in oracle or "whenever this creature attacks" in oracle:
        rewards["protection"] = rewards.get("protection", 0.0) + 1.5
        rewards["archetype_core"] = rewards.get("archetype_core", 0.0) + 1.0

    # Token rewards.
    if "create" in oracle and "token" in oracle:
        rewards["archetype_core"] = rewards.get("archetype_core", 0.0) + 1.5

    # Graveyard rewards recursion.
    if "graveyard" in oracle and ("return" in oracle or "exile" in oracle):
        rewards["recursion"] = rewards.get("recursion", 0.0) + 1.5

    # Doubling effect rewards everything.
    if "triggers an additional time" in oracle or "twice" in oracle or "double" in oracle:
        rewards["archetype_core"] = rewards.get("archetype_core", 0.0) + 2.0
        rewards["synergy_enablers"] = rewards.get("synergy_enablers", 0.0) + 1.5

    return rewards


# ─── Dependency score ─────────────────────────────────────────────────────────

def _score_dependency(oracle: str, type_line: str, mv: float, archetype: str) -> float:
    score = 5.0

    # Strong engine signals.
    if "whenever" in oracle:
        score += 1.5
    if "draw" in oracle and ("a card" in oracle or "cards" in oracle):
        score += 1.0
    if "add {" in oracle or (
        "search your library for a" in oracle and "land" in oracle
    ):
        score += 1.0
    if "triggers an additional time" in oracle or "twice" in oracle:
        score += 1.5

    # Near-vanilla oracle text → low dependency.
    if len(oracle.strip()) < 50:
        score -= 2.0

    # Archetype match bonus.
    if archetype in _ARCHETYPE_FIT_KEYWORDS:
        kws = _ARCHETYPE_FIT_KEYWORDS[archetype]
        text = oracle + " " + type_line
        if sum(1 for kw in kws if kw in text.lower()) >= 2:
            score += 1.0

    # Cheap commander can be recast more easily.
    if mv <= 2:
        score -= 0.5
    elif mv >= 6:
        score += 0.5

    return max(0.0, min(10.0, score))


# ─── Threat reputation ────────────────────────────────────────────────────────

def _score_threat(oracle: str, type_line: str, mv: float, archetype: str) -> float:
    score = 4.0

    if "draw" in oracle and ("a card" in oracle or "cards" in oracle):
        score += 2.0
    if "add {" in oracle:
        score += 2.0
    if "search your library for a card" in oracle:
        score += 2.0
    if "triggers an additional time" in oracle or "twice" in oracle or "double" in oracle:
        score += 3.0
    if "costs {" in oracle and "less" in oracle:
        score += 2.0
    if "you may cast" in oracle and "without paying" in oracle:
        score += 2.5
    if mv <= 3:
        score += 1.0
    if archetype in ("combo", "stax"):
        score += 2.0
    elif archetype in ("control", "theft"):
        score += 1.0

    return max(0.0, min(10.0, score))


# ─── Combo potential ─────────────────────────────────────────────────────────

def _score_combo_potential(oracle: str, archetype: str) -> float:
    score = 1.0
    if "untap" in oracle:
        score += 2.5
    if "triggers an additional time" in oracle or "twice" in oracle:
        score += 2.0
    if "you may cast" in oracle and ("free" in oracle or "without paying" in oracle):
        score += 2.5
    if "copy" in oracle:
        score += 1.5
    if archetype in ("combo",):
        score += 2.0
    return max(0.0, min(10.0, score))


# ─── MV pressure ─────────────────────────────────────────────────────────────

def score_mv_pressure(mv: float) -> float:
    mv_int = int(mv)
    if mv_int >= 7:
        return MV_PRESSURE_HIGH
    return MV_PRESSURE_TABLE.get(mv_int, MV_PRESSURE_TABLE.get(min(mv_int, 6), 0.0))


# ─── Main commander scoring entry point ──────────────────────────────────────

def score_commander(card_data: Dict[str, Any], archetype: str) -> Dict[str, Any]:
    """
    Compute commander scores from card data.

    Returns a dict with dependency, threat_reputation, mana_value_pressure,
    built_in_* convenience fields, combo_potential, provides, requires, rewards.
    """
    oracle = (card_data.get("oracle_text") or "").lower()
    type_line = (card_data.get("type_line") or "").lower()
    mv = float(card_data.get("mana_value") or 0)

    provides = _score_provides(oracle)
    requires = _score_requires(oracle, mv)
    rewards = _score_rewards(oracle, type_line, archetype)
    dependency = _score_dependency(oracle, type_line, mv, archetype)
    threat = _score_threat(oracle, type_line, mv, archetype)
    mv_pressure = score_mv_pressure(mv)
    combo_potential = _score_combo_potential(oracle, archetype)

    return {
        "dependency": round(dependency, 2),
        "threat_reputation": round(threat, 2),
        "mana_value_pressure": mv_pressure,
        "built_in_card_advantage": round(provides.get("draw", 0.0), 2),
        "built_in_ramp": round(provides.get("normal_ramp", 0.0), 2),
        "built_in_removal": round(provides.get("targeted_removal", 0.0), 2),
        "built_in_protection": round(provides.get("protection", 0.0), 2),
        "combo_potential": round(combo_potential, 2),
        "provides": {k: round(v, 2) for k, v in provides.items()},
        "requires": {k: round(v, 2) for k, v in requires.items()},
        "rewards": {k: round(v, 2) for k, v in rewards.items()},
    }


def merge_partner_scores(
    score_a: Dict[str, Any],
    score_b: Dict[str, Any],
) -> Dict[str, Any]:
    """Combine two partner commander scores. Takes max for most fields."""

    def _merge_dict(da: dict, db: dict) -> dict:
        keys = set(da) | set(db)
        return {k: max(da.get(k, 0.0), db.get(k, 0.0)) for k in keys}

    return {
        "dependency": round(max(score_a["dependency"], score_b["dependency"]), 2),
        "threat_reputation": round(
            max(score_a["threat_reputation"], score_b["threat_reputation"]), 2
        ),
        "mana_value_pressure": round(
            max(score_a["mana_value_pressure"], score_b["mana_value_pressure"]), 2
        ),
        "built_in_card_advantage": round(
            max(score_a["built_in_card_advantage"], score_b["built_in_card_advantage"]), 2
        ),
        "built_in_ramp": round(
            max(score_a["built_in_ramp"], score_b["built_in_ramp"]), 2
        ),
        "built_in_removal": round(
            max(score_a["built_in_removal"], score_b["built_in_removal"]), 2
        ),
        "built_in_protection": round(
            max(score_a["built_in_protection"], score_b["built_in_protection"]), 2
        ),
        "combo_potential": round(
            max(score_a["combo_potential"], score_b["combo_potential"]), 2
        ),
        "provides": _merge_dict(score_a["provides"], score_b["provides"]),
        "requires": _merge_dict(score_a["requires"], score_b["requires"]),
        "rewards": _merge_dict(score_a["rewards"], score_b["rewards"]),
    }
