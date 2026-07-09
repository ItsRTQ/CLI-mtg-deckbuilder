"""Single source for commander-plan coverage over a deck (2026-07-06).

Two consumers share this so they can never drift (the recurring multi-consumer
root cause): `deck-gaps`' Commander plan check and `deck-power`'s synergy density.
The plan→function map is the analyzer's OWN vocabulary — mapping._ARCHETYPE_RULES
defining+supporting tokens that are card_tags names — plus type_line counting for
tribal bands. Matching goes through utils.phrase_match (wildcard-aware).
"""
from typing import Any, Dict, List, Optional

from mtgcli.utils.phrase_match import any_phrase_matches


def _card_text(card: Dict[str, Any]) -> str:
    return " ".join([card.get("name", "") or "", card.get("type_line", "") or "",
                     card.get("oracle_text", "") or ""]).lower()


def plan_coverage(commander_card: Dict[str, Any], deck_cards: List[Dict[str, Any]],
                  tag_defs: Dict[str, List[str]]) -> Optional[Dict[str, Any]]:
    """Coverage of the commander's detected plan over the deck.

    Returns {"bands": [{archetype, band, plan_tags, have, cards}], "covered_cards": [...],
             "synergy_density": float, "nonland_count": int} or None when the analyzer
    reads no high bands (an honest empty — density would be meaningless, not zero).
    """
    from mtgcli.analyzer.analyze import analyze_card
    from mtgcli.analyzer.mapping import _ARCHETYPE_RULES

    ua = analyze_card(commander_card)
    high = [s for s in ua.get("archetype_support", [])
            if s.get("band") in ("high", "very_high")]
    if not high:
        return None

    nonland = [c for c in deck_cards if "land" not in (c.get("type_line") or "").lower()]
    bands = []
    covered: Dict[str, bool] = {}
    for s in high:
        arch = s["archetype"]
        members: List[str] = []
        plan_tags: List[str] = []
        if arch.endswith(" Tribal"):
            ttype = arch[: -len(" Tribal")].lower()
            for c in deck_cards:
                if ttype in (c.get("type_line") or "").lower():
                    members.append(c.get("name", ""))
        else:
            rules = _ARCHETYPE_RULES.get(arch, {})
            plan_tags = [t for t in list(rules.get("defining", [])) + list(rules.get("supporting", []))
                         if t in tag_defs]
            if not plan_tags:
                bands.append({"archetype": arch, "band": s["band"], "plan_tags": [],
                              "have": 0, "cards": []})
                continue
            phrases = [p for t in plan_tags for p in tag_defs[t]]
            for c in deck_cards:
                if any_phrase_matches(phrases, _card_text(c)):
                    members.append(c.get("name", ""))
        for name in members:
            covered[name] = True
        have = sum(c.get("quantity", 1) for c in deck_cards if c.get("name", "") in set(members))
        bands.append({"archetype": arch, "band": s["band"], "plan_tags": plan_tags,
                      "have": have, "cards": members})

    # Density over NONLAND names (lands serve mana, not the plan; basics would drown it).
    nonland_names = {c.get("name", "") for c in nonland}
    covered_nonland = [n for n in covered if n in nonland_names]
    density = round(len(covered_nonland) / len(nonland_names), 3) if nonland_names else 0.0
    return {
        "bands": bands,
        "covered_cards": sorted(covered_nonland),
        "synergy_density": density,
        "nonland_count": len(nonland_names),
    }
