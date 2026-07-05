"""Map signals + tags to archetype/role support — using ordinal BUCKETS, never magic sums.

The core anti-magic-number rule: a card's support for an archetype is classified qualitatively
(very_high / high / medium / low / none) from WHICH KIND of evidence it has — a defining signal
weighs categorically more than several weak hints. Four weak hints never "add up" to one defining
signal, because they live in different buckets, not on one number line.

Content evidence (what the card does) comes from the existing 97-tag vocabulary so we don't build
a parallel content detector; the new analyzer's structural/semantic signals (scope, timing,
negation, verb/noun) refine and correct it.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List

from mtgcli.analyzer.model import CardProfile, Trace


# archetype -> {strength: [evidence tokens]}. Evidence tokens are signal IDs or tag names.
# strength is "defining" (alone implies the archetype), "supporting", or "weak".
_ARCHETYPE_RULES: Dict[str, Dict[str, List[str]]] = {
    "Voltron": {
        "defining": ["COMBAT_DAMAGE_TRIGGER", "voltron_payoff", "aura_equipment_payoff"],
        "supporting": ["DAMAGE_SCALING", "UNBLOCKABLE", "aura", "equipment", "double_strike"],
        "weak": [],
    },
    "Aristocrats": {
        "defining": ["death_trigger", "aristocrats", "DOUBLES_DEATH_TRIGGERS"],
        "supporting": ["sacrifice_outlet", "free_sacrifice_outlet", "SAC_OUTLET", "UTILITY_TOKEN_MAKER", "token_maker", "reanimation", "EVOKE"],
        "weak": ["lifedrain"],
    },
    "Life Loss / Group Slug": {
        "defining": ["group_slug", "LOST_LIFE_PAYOFF"],
        "supporting": ["TRIGGER_LIFE_CHANGE", "lifedrain", "lifegain_payoff", "extort"],
        "weak": [],
    },
    "Counters Matter": {
        "defining": ["COUNTER_MARKER", "counter_payoff"],
        "supporting": ["counter_enabler", "proliferate"],
        "weak": [],
    },
    "Minus Counters / Attrition": {
        "defining": ["COUNTER_MARKER_MINUS"],
        "supporting": ["proliferate", "wither", "infect"],
        "weak": [],
    },
    "Attack Triggers / Aggro": {
        "defining": ["TRIGGER_ATTACKS_OR_COMBAT", "DOUBLES_ATTACK_TRIGGERS", "extra_combat", "attack_trigger_payoff"],
        "supporting": ["go_wide_payoff", "double_strike", "haste"],
        "weak": [],
    },
    "Vehicles": {
        "defining": ["VEHICLE"],
        "supporting": ["artifact_payoff", "crew"],
        "weak": [],
    },
    "Spellslinger": {
        "defining": ["spell_payoff", "magecraft", "spell_copy"],
        "supporting": ["COUNTERSPELL_INTERACTION"],
        "weak": [],
    },
    "Stax / Prison": {
        # TAX_COST_INCREASE promoted to defining (batch-13 GAAIV finding): a GENERAL cost
        # tax IS the prison plan. Safe because the detector routes targeting-conditional
        # taxes (the Kopala/Charix protection class) to TARGETED_TAX, which never feeds Stax.
        "defining": ["ATTACK_RESTRICTION", "CAST_RESTRICTION", "UNTAP_RESTRICTION", "stax",
                     "TAX_COST_INCREASE"],
        "supporting": ["tax", "BLOCK_RESTRICTION"],
        "weak": [],
    },
    "Punisher / Asymmetric": {
        "defining": [],
        "supporting": ["SCOPE_OPPOSING_CREATURES", "SCOPE_OPPOSING_PERMANENTS", "SCOPE_EACH_OPPONENT"],
        "weak": [],
    },
    "Go Wide": {
        "defining": ["go_wide_payoff", "REPEATABLE_TOKEN_MAKER"],
        "supporting": ["token_maker", "anthem"],
        "weak": [],
    },
    "Reanimator": {
        "defining": ["reanimation"],
        "supporting": ["self_mill", "discard_outlet", "graveyard_recursion"],
        "weak": [],
    },
    "Blink / Flicker": {
        "defining": ["blink"],
        "supporting": ["etb_value", "TRIGGER_PERMANENT_ENTERS", "DOUBLES_ETB_TRIGGERS"],
        "weak": [],
    },
    "ETB Value": {
        "defining": ["DOUBLES_ETB_TRIGGERS"],
        "supporting": ["TRIGGER_PERMANENT_ENTERS", "etb_value", "blink"],
        "weak": [],
    },
    "Theft": {
        "defining": ["theft", "THEFT_CONTROL", "THEFT_EXILE"],
        "supporting": [],
        "weak": [],
    },
    "Legendary Matters": {
        "defining": ["LEGENDARY_MATTERS"],
        "supporting": ["legendary_payoff", "historic"],
        "weak": [],
    },
    "Treasures / Value Engine": {
        "defining": ["REPEATABLE_VALUE_TOKENS"],
        "supporting": ["treasure"],
        "weak": [],
    },
    "Graveyard Value / Recursion": {
        # GRAVEYARD_CLONE (batch-16): same-line graveyard+copy conjunction — 90 cards
        # measured, all genuine graveyard value (Feldon, Lazav, Scarab God, embalm cycle).
        "defining": ["graveyard_recast", "GRAVEYARD_CLONE"],
        "supporting": ["graveyard_recursion", "self_mill", "GRAVEYARD_SCALING"],
        "weak": [],
    },
    "Morph / Face-down": {
        "defining": ["morph_facedown"],
        "supporting": [],
        "weak": [],
    },
    "Battlecruiser / Big Mana": {
        "defining": ["battlecruiser"],
        "supporting": ["ramp"],
        "weak": [],
    },
    "Toughness / Defenders": {
        "defining": ["toughness_matters"],
        "supporting": [],
        "weak": [],
    },
    "Stompy / Big Power": {
        "defining": ["POWER_MATTERS"],
        "supporting": ["ramp", "land_ramp"],
        "weak": [],
    },
    "Toolbox / Goodstuff": {
        "defining": ["MODAL_TOOLBOX"],
        "supporting": [],
        "weak": [],
    },
    "Wheels / Forced Draw": {
        "defining": ["wheel"],
        "supporting": ["TRIGGER_DRAW_OR_DISCARD"],
        "weak": [],
    },
    "Artifacts Matter": {
        "defining": ["artifact_payoff"],
        "supporting": ["artifact_recursion"],
        "weak": [],
    },
    "Group Hug / Politics": {
        # MONARCH defining (batch-14): claiming/granting the crown is a politics plan —
        # measured 13 commanders, all monarch-politics builds.
        "defining": ["group_hug", "DONATION", "MONARCH"],
        "supporting": [],
        "weak": [],
    },
    "Mill": {
        "defining": ["mill_opponents"],
        "supporting": [],
        "weak": [],
    },
    "Superfriends / Planeswalkers": {
        "defining": ["superfriends"],
        "supporting": ["proliferate"],
        "weak": [],
    },
    "Lands / Landfall": {
        "defining": ["landfall", "land_payoff"],
        "supporting": ["extra_land_drop", "land_recursion"],
        "weak": [],
    },
}


@dataclass
class ArchetypeSupport:
    archetype: str
    defining: List[str] = field(default_factory=list)
    supporting: List[str] = field(default_factory=list)
    weak: List[str] = field(default_factory=list)

    def band(self) -> str:
        if self.defining:
            return "very_high" if len(self.supporting) >= 2 else "high"
        if len(self.supporting) >= 2:
            return "medium"
        if self.supporting or self.weak:
            return "low"
        return "none"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "archetype": self.archetype,
            "band": self.band(),
            "defining": self.defining,
            "supporting": self.supporting,
            "weak": self.weak,
        }


# Wide-vs-tall exclusion (batch-16 Chishiro CW): a card cannot be a one-threat Voltron plan
# AND a board-wide army plan at once. When the evidence shows BOTH an army builder
# (REPEATABLE_TOKEN_MAKER) and a board-wide pump (broad COUNTER_MARKER — each/target scope,
# never the SELF variant), an aura/equipment payoff supports the WIDE-modified plan, so it
# demotes from Voltron's defining to supporting. Measured over the 24 commanders carrying
# aura_equipment_payoff: only the Chishiro class has both wide signals; Sram/Galea/Wyleth
# (no army), Kemba/Stangg (tokens but no broad pump) keep their Voltron reads.
_WIDE_ARMY_SIGNALS = {"REPEATABLE_TOKEN_MAKER", "COUNTER_MARKER"}


def map_archetypes(evidence: set) -> List[ArchetypeSupport]:
    """Given the set of evidence tokens a card has (signal IDs + tag names), return per-archetype
    support classified into ordinal bands. No summation: a token only ever lands in its bucket."""
    out: List[ArchetypeSupport] = []
    wide_army = _WIDE_ARMY_SIGNALS <= evidence
    for arch, rules in _ARCHETYPE_RULES.items():
        sup = ArchetypeSupport(archetype=arch)
        for tok in rules.get("defining", []):
            if tok in evidence:
                if wide_army and arch == "Voltron" and tok == "aura_equipment_payoff":
                    sup.supporting.append(tok)
                    continue
                sup.defining.append(tok)
        for tok in rules.get("supporting", []):
            if tok in evidence:
                sup.supporting.append(tok)
        for tok in rules.get("weak", []):
            if tok in evidence:
                sup.weak.append(tok)
        if sup.band() != "none":
            out.append(sup)

    # Tribal is dynamic (the type varies: Dinosaur, Elf, ...), so it can't be a static rule.
    # Any TRIBAL_<TYPE> signal defines a "<Type> Tribal" archetype.
    tribal_types = sorted({tok.split("TRIBAL_", 1)[1].capitalize()
                           for tok in evidence if tok.startswith("TRIBAL_")})
    for ttype in tribal_types:
        out.append(ArchetypeSupport(archetype=f"{ttype} Tribal", defining=[f"TRIBAL_{ttype.upper()}"]))

    # Order by band strength then by name for stability.
    band_rank = {"very_high": 4, "high": 3, "medium": 2, "low": 1, "none": 0}
    out.sort(key=lambda s: (-band_rank[s.band()], s.archetype))
    return out
