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
        # attacks_alone (batch #20, the Rafiq/exalted class — 95 measured, incl. every
        # exalted reminder): SUPPORTING, not defining — Noble Hierarch carries exalted
        # but is a mana dork, not a Voltron plan by herself.
        "defining": ["COMBAT_DAMAGE_TRIGGER", "voltron_payoff", "aura_equipment_payoff"],
        "supporting": ["DAMAGE_SCALING", "UNBLOCKABLE", "aura", "equipment", "double_strike",
                       "attacks_alone"],
        "weak": [],
    },
    "Aristocrats": {
        "defining": ["death_trigger", "aristocrats", "DOUBLES_DEATH_TRIGGERS"],
        "supporting": ["sacrifice_outlet", "free_sacrifice_outlet", "SAC_OUTLET", "UTILITY_TOKEN_MAKER", "token_maker", "reanimation", "EVOKE", "exploit"],
        "weak": ["lifedrain"],
    },
    "Life Loss / Group Slug": {
        "defining": ["group_slug", "LOST_LIFE_PAYOFF"],
        "supporting": ["TRIGGER_LIFE_CHANGE", "lifedrain", "lifegain_payoff", "extort"],
        "weak": [],
    },
    "Counters Matter": {
        # dethrone (known-gaps session 2): keyword, 10 measured, every dethrone card
        # places +1/+1 counters by mechanics — supporting, so Marchesa BR (dethrone +
        # counter_enabler = 2 supporting) reads medium instead of the batch #14/#15
        # co-primary underband at low. Deliberately NOT defining (a single dethrone
        # creature is not a counters plan by itself).
        "defining": ["COUNTER_MARKER", "counter_payoff"],
        "supporting": ["counter_enabler", "proliferate", "dethrone"],
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
        # vehicle_payoff (coverage fix round post-#18): the Greasefang class —
        # "vehicle card from your graveyard" (8), "vehicles/vehicle you control"
        # (25/39), "whenever a vehicle" (10) — vehicle-MATTERS payoffs, distinct
        # from the VEHICLE signal (being one).
        "defining": ["VEHICLE", "vehicle_payoff"],
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
        # THEFT_TOPDECK (coverage fix round post-#18): the Xanathar class — "you may
        # play the top card of their library" grants access without exile (37 measured).
        "defining": ["theft", "THEFT_CONTROL", "THEFT_EXILE", "THEFT_TOPDECK"],
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
        "supporting": ["treasure", "investigate"],
        "weak": [],
    },
    "Graveyard Value / Recursion": {
        # GRAVEYARD_CLONE (batch-16): same-line graveyard+copy conjunction — 90 cards
        # measured, all genuine graveyard value (Feldon, Lazav, Scarab God, embalm cycle).
        "defining": ["graveyard_recast", "GRAVEYARD_CLONE"],
        "supporting": ["graveyard_recursion", "self_mill", "GRAVEYARD_SCALING", "escape_gy"],
        "weak": [],
    },
    "Morph / Face-down": {
        "defining": ["morph_facedown"],
        "supporting": [],
        "weak": [],
    },
    "Snow Matters": {
        # Batch #19 (the Jorn class): "snow permanent" (24 measured, all payoffs —
        # Ice-Fang Coatl, Isu). "snow land" REJECTED (Thermokarst land-hate FPs);
        # "snow creature" REJECTED ("non-snow creature" negation FPs).
        "defining": ["snow_payoff"],
        "supporting": [],
        "weak": [],
    },
    "Gates Matter": {
        # Batch #19 (the Nine-Fingers Keene class): "gate card" 9 + "gate(s) you
        # control" 6/14 — the Maze's End/Basilisk Gate family, all genuine.
        "defining": ["gates_payoff"],
        "supporting": [],
        "weak": [],
    },
    "Dungeons / Venture": {
        # Batch #19 (the Sefris class): "venture into the dungeon" 46 +
        # "complete(d) a dungeon" 21 — keyword-action family, all genuine.
        "defining": ["dungeon_payoff"],
        "supporting": [],
        "weak": [],
    },
    "Cascade": {
        # Batch #19 (the Yidris class): "cascade" 55 — keyword family (holders and
        # granters alike are cascade-deck cards).
        "defining": ["cascade"],
        "supporting": [],
        "weak": [],
    },
    "Goad / Forced Combat": {
        # Batch #19 (the Marisi class): "goad" 85 — keyword family.
        "defining": ["goad"],
        "supporting": [],
        "weak": [],
    },
    "Mutate": {
        # Batch #20 (the Otrimi class): "mutate" 39 — keyword family.
        "defining": ["mutate"],
        "supporting": [],
        "weak": [],
    },
    "Targeted Spell Payoff / Heroic": {
        # Post-#25 fix round: the Gargos/Anax/Ivy family (3+ commanders). Measured:
        # "heroic —" 46 (ability word), "you control becomes the target of a spell" 25
        # (payoff AND deterrent readings both want self-target spell density),
        # "spell that targets only a single" 12 (the Ivy/Precursor copy family).
        "defining": ["targeted_spell_payoff"],
        "supporting": [],
        "weak": [],
    },
    "Dice Rolling": {
        # Post-#25 fix round: the Wyll/Mr. House class (2 commanders). "whenever you
        # roll" 26 + "roll one or more dice" 11 — payoff forms only (d20/d6 rollers
        # deliberately not defining).
        "defining": ["dice_payoff"],
        "supporting": [],
        "weak": [],
    },
    "Flash / Instant Speed": {
        # Post-#25 fix round: the Raff/Errant-and-Giada class (2 commanders).
        # "as though they/it had flash" 47+43 + "spells with flash" 3.
        "defining": ["flash_enabler"],
        "supporting": [],
        "weak": [],
    },
    "Storm": {
        # Post-#25 fix round (the Aeve class): "storm (" keyword-with-reminder 42 +
        # "has storm" 2. The naked "storm" substring REJECTED — 19 self-reference FPs
        # (Windstorm/Starstorm-named cards).
        "defining": ["storm_payoff"],
        "supporting": [],
        "weak": [],
    },
    "Ninjutsu / Sneak": {
        # Post-#25 fix round (the Satoru class): "ninjutsu" 50, keyword family.
        "defining": ["ninjutsu"],
        "supporting": [],
        "weak": [],
    },
    "Adventures Matter": {
        # Post-#25 fix round (the Gorion class): "adventure" in oracle = payoffs (25;
        # Adventure CARDS carry it in the type line, not oracle).
        "defining": ["adventure_payoff"],
        "supporting": [],
        "weak": [],
    },
    "Cycling": {
        # Post-#25 fix round (the Gavi class): "you cycle" 86 + "cycle or discard" 14.
        "defining": ["cycling_payoff"],
        "supporting": [],
        "weak": [],
    },
    "Pillowfort / Defense": {
        # Batch #22 (the Isperia CW class): opponents attacking YOU is a defense
        # payoff (19 measured incoming-attack triggers, all pillowfort — Marchesa's
        # Decree, Revenge of Ravens) + the existing pillowfort tag.
        "defining": ["pillowfort", "INCOMING_ATTACK_TRIGGER"],
        "supporting": [],
        "weak": [],
    },
    "Sagas Matter": {
        # Batch #22 (the Tom Bombadil class): saga-payoff forms measured ~15 clean
        # ("saga(s) you control", "final chapter", "saga card"). "lore counter"
        # REJECTED — 239 matches, every printed Saga would read the archetype.
        "defining": ["saga_payoff"],
        "supporting": [],
        "weak": [],
    },
    "Enchantments Matter": {
        # Coverage fix round post-#18 (the Anikthea class — the parallel of Artifacts
        # Matter that never existed). Measured: "constellation" 35, "whenever an
        # enchantment you control enters" 37, "whenever you cast an enchantment" 19,
        # "enchantments you control" 13; recursion "enchantment card from your
        # graveyard" 40. "enchantment spell" REJECTED (8 counterspell FPs — Annul).
        # NOTE: deliberately not the legacy `enchantress` tag — it carries a naked
        # "draw a card" phrase (landmine, annotated).
        "defining": ["enchantment_payoff"],
        "supporting": ["enchantment_recursion"],
        "weak": [],
    },
    "Energy": {
        # Coverage fix round post-#18 (the Satya class): "{e}" — 146 measured, the
        # energy-counter symbol appears only on energy cards.
        "defining": ["energy"],
        "supporting": [],
        "weak": [],
    },
    "Forced Discard": {
        # Coverage fix round post-#18 (the Tinybones/Nath/Megrim class — opponent-
        # discard matters, distinct from self-discard/Wheels). Measured: "whenever an
        # opponent discards" 15, "each opponent discards" 68, "an opponent discarded"
        # 1 (Tinybones' threshold form rides the family).
        "defining": ["opponent_discard_payoff"],
        "supporting": [],
        "weak": [],
    },
    "Clones / Copies": {
        # Coverage fix round post-#18 (partial close of the old Volo gap): "token
        # that's a copy" 352 + "as a copy of" 75 (the Clone/Clever Impersonator class),
        # all genuine copy-value. "copy target" REJECTED (Fork/Twincast spell-copy is
        # Spellslinger territory); Volo's own "copy that spell" form stays unread
        # (dragging it in would misband Krark/Jin-Gitaxias — annotated).
        "defining": ["clone_copy"],
        "supporting": [],
        "weak": [],
    },
    "Poison / Infect": {
        # Batch #18: the poison tag (infect 70 / toxic 71 / "poison counter" 182)
        # existed but no archetype consumed it — Fynn read only Attack Triggers.
        # Pure mapping fix: measured vocabulary was already there.
        "defining": ["poison"],
        "supporting": ["proliferate"],
        "weak": [],
    },
    "Party": {
        # Batch #18: the Burakos class — "in your party" (31 measured, all genuine
        # party-scaling payoffs: Squad Commander, Deadly Alliance).
        "defining": ["party_payoff"],
        "supporting": [],
        "weak": [],
    },
    "Amass / Army": {
        # Known-gaps session 2: the Sauron amass class (batch #16 gap). "amass" is a
        # keyword — 60 measured, all genuine (incl. conjugated "amasses"); "army you
        # control" (52) covers the Army payoffs. One growing token: counters-adjacent,
        # not Go Wide.
        "defining": ["amass_payoff"],
        "supporting": [],
        "weak": [],
    },
    "Pingers / Damage Matters": {
        # Known-gaps session 2: the Ghyrson Starn pinger-payoff class (batch #14 gap).
        # Measured union: 19 cards, all genuine damage-payoffs ("deals exactly" is
        # Ghyrson's unique threshold form; "whenever a source you control deals" /
        # "deals noncombat damage" are the Taii Wakeen/Niv-Mizzet Visionary/Thor class).
        # NOTE: deliberately NOT the pre-existing broad `damage_payoff` tag — its
        # "whenever a creature deals combat damage" phrase is saboteur/attack territory.
        "defining": ["pinger_payoff"],
        "supporting": [],
        "weak": [],
    },
    "X Spells Matter": {
        # Known-gaps session 2: the Zaxara X-spell payoff class (batch #15 gap).
        # Measured phrases: "cast a spell with {x}" (7, all genuine payoffs — Zaxara,
        # Magus Lucea Kane, Elementalist's Palette), "costs that contain {x}" (4 —
        # the Rosheen X-mana class), "contains {x}" (2 — Unbound Flourishing).
        # The hate forms (Gaddock Teeg "with {X} in their mana costs", Frontline
        # Medic's counter) are excluded by the directional cast/cost anchors.
        "defining": ["x_spell_payoff"],
        "supporting": [],
        "weak": [],
    },
    "Creature Spells Matter": {
        # Known-gaps session 2: the Animar/Chulane cast-creature engine class (batch
        # #14/#15 gap). Measured phrases: "whenever you cast a creature spell" (72,
        # all genuine payoffs), "creature spells you cast cost" (28, cost reducers —
        # the "you cast" anchor excludes Thalia-style taxers), "each creature spell
        # you cast" (4 — Henzie, Herigast).
        "defining": ["creature_cast_payoff"],
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
        # discard_payoff (known-gaps session 2): "whenever you discard" — 48 measured,
        # all genuine discard-payoffs (Rielle's "one or more cards for the first time",
        # Anje's madness untap, Inti, Glint-Horn). Closes the batch #15 Rielle wheel-vocab
        # gap AND the batch #16 madness/Anje gap in one directional phrase.
        # draw_trigger_payoff (known-gaps session 2): "whenever you draw a card" (48) /
        # "your second card" (51) — all draw-payoff engines (Locust God, Niv-Mizzet,
        # Sheoldred, Chasm Skulker); a per-draw payoff commander wants maximum forced
        # draw. Closes the batch #16 Locust God co-primary underband.
        "defining": ["wheel", "discard_payoff", "draw_trigger_payoff"],
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
        # EXILE_MILL (pre-build fix round): targeted top-of-library exile with no play
        # permission — the Circu/Ashiok class (4 measured, all genuine; the play-
        # permission forms are Theft, the each-player forms measured theft/hug-dirty).
        "defining": ["mill_opponents", "EXILE_MILL"],
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
                # Conditional-rider exclusion (batch #22, the Raggadragga/Hallar class):
                # a "whenever you cast a spell, IF <non-spell-type rider>" trigger is not
                # spellslinger density — its spell_payoff hit demotes to supporting.
                if ("CONDITIONAL_CAST_RIDER" in evidence and arch == "Spellslinger"
                        and tok == "spell_payoff"):
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
