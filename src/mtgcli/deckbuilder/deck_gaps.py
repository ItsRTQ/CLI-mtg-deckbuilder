"""Deck-gap audit core — the SINGLE source shared by the CLI (`mtg deck-gaps`)
and the GUI API (`GET /api/decks/{name}/gaps`).

Cross-references the category-count targets and the commander's oracle hooks
against what the deck actually contains, plus the analyzer plan check
(plan_coverage — same band-matching implementation as deck-power). Extracted
from the CLI command so a second consumer can't drift (the multi-consumer
lesson: one implementation, many presenters).

Each gap carries BOTH a ready CLI `fill_command` (the agent's interface) and a
structured `fill` dict (`{"tags": [...], "query": ..., "type": ..., "colors": ...}`)
so GUI consumers can prefill a search without parsing command strings.
"""
import json
from typing import Any, Dict, List, Optional

from mtgcli.config import SEED_DATA_DIR, SQLITE_PATH

PLAN_MIN = 5  # fewer than this many cards serving a detected plan = thin


def _fill(colors: str, *, tags: Optional[List[str]] = None,
          query: Optional[str] = None, type_: Optional[str] = None) -> Dict[str, Any]:
    return {"tags": tags or [], "query": query, "type": type_, "colors": colors}


def compute_deck_gaps(
    commander: str,
    entries: List[Dict[str, Any]],
    repo,
    *,
    archetype: str = "midrange",
    partner: Optional[str] = None,
    power_level: int = 7,
) -> Dict[str, Any]:
    """Audit `entries` ([{"name", "quantity"}] main-deck rows) against the
    commander's plan. Returns the deck-gaps result dict (gaps ranked by need)."""
    from mtgcli.cards.search import _load_role_definitions
    from mtgcli.category_counts.calculator import calculate_category_counts
    from mtgcli.deckbuilder.deck_check import _get_category_phrases
    from mtgcli.deckbuilder.oracle_hooks import extract_hooks
    from mtgcli.utils.phrase_match import any_phrase_matches

    # Hydrate so phrases match against real oracle text.
    deck_cards = []
    for e in entries:
        cd = repo.get_card_by_exact_name(e.get("name", "")) if e.get("name") else None
        if cd:
            cd = dict(cd)
            cd["quantity"] = e.get("quantity", 1)
            deck_cards.append(cd)

    tag_defs = json.load(open(SEED_DATA_DIR / "card_tags.json", encoding="utf-8"))
    role_defs = _load_role_definitions()

    def _matching(phrases):
        """(count, names) of deck cards matching any phrase — names let the audit
        SHOW what it counted (the fix-or-justify decision needs the list)."""
        n, names = 0, []
        for c in deck_cards:
            text = " ".join([c.get("name", "") or "", c.get("type_line", "") or "",
                             c.get("oracle_text", "") or ""]).lower()
            if any_phrase_matches(phrases, text):
                n += c.get("quantity", 1)
                names.append(c.get("name", ""))
        return n, names

    def _count_matching(phrases):
        return _matching(phrases)[0]

    cmd_card = repo.get_card_by_exact_name(commander)
    colors = "".join((cmd_card or {}).get("color_identity", []))

    cc = calculate_category_counts(commander, archetype, partner_name=partner,
                                   power_level=power_level, db_path=str(SQLITE_PATH))

    gaps = []
    for rec in cc.get("category_recommendations", []):
        cat = rec["category"]
        min_count = rec.get("min_count", 0)
        phrases = _get_category_phrases(cat, tag_defs, role_defs)
        if not phrases:
            continue
        have = _count_matching(phrases)
        if have < min_count:
            gaps.append({
                "category": cat,
                "display_name": rec.get("display_name", cat),
                "have": have,
                "want_at_least": min_count,
                "recommended_range": rec.get("recommended_range"),
                "need_score": rec.get("need_score", 0),
                "fill_command": f"mtg search-tags {cat} --colors {colors} --json-output",
                "fill": _fill(colors, tags=[cat]),
            })

    # Oracle-hook signal gaps: things the commander's text specifically wants.
    hook_gaps = []
    hook_gap_fills = []
    if cmd_card:
        hooks = extract_hooks(cmd_card.get("oracle_text", "") or "")
        custom = [c for c in hooks["named_counters"] if c not in ("+1/+1", "-1/-1")]
        if custom and _count_matching(_get_category_phrases("proliferate", tag_defs, role_defs)) == 0:
            msg = (f"Commander uses '{', '.join(custom)}' counters but the deck has "
                   "no proliferate — add proliferate (search-tags proliferate).")
            hook_gaps.append(msg)
            hook_gap_fills.append({"message": msg,
                                   "fill": _fill(colors, tags=["proliferate"])})

    # Audit the deck against the ANALYZER's read of the commander: for every
    # high/very_high band, count the deck cards serving that plan. Single source
    # with deck-power's synergy density (plan_coverage). Guarded: an analyzer
    # failure only drops this section.
    analyzer_support = []
    plan_gaps = []
    if cmd_card:
        try:
            from mtgcli.deckbuilder.plan_coverage import plan_coverage
            pc = plan_coverage(cmd_card, deck_cards, tag_defs)
            for b in (pc["bands"] if pc else []):
                arch = b["archetype"]
                if arch.endswith(" Tribal"):
                    ttype = arch[: -len(" Tribal")].lower()
                    fill_cmd = f"mtg search --subtype {ttype} --type creature --colors {colors}"
                    fill = _fill(colors, query=f"type:{ttype}", type_="creature")
                elif not b["plan_tags"]:
                    analyzer_support.append({"archetype": arch, "band": b["band"]})
                    continue
                else:
                    fill_cmd = f"mtg search-tags {' '.join(b['plan_tags'][:3])} --colors {colors}"
                    fill = _fill(colors, tags=b["plan_tags"][:3])
                # Every audited band exposes WHICH cards were counted, gap or not.
                analyzer_support.append({"archetype": arch, "band": b["band"],
                                         "have": b["have"], "cards": b["cards"]})
                if b["have"] < PLAN_MIN:
                    plan_gaps.append({
                        "archetype": arch,
                        "band": b["band"],
                        "have": b["have"],
                        "cards": b["cards"],
                        "want_at_least": PLAN_MIN,
                        "fill_command": fill_cmd,
                        "fill": fill,
                    })
        except Exception:
            analyzer_support = []
            plan_gaps = []

    gaps.sort(key=lambda g: -g["need_score"])
    return {"commander": commander, "archetype": archetype, "colors": colors,
            "gaps": gaps, "hook_gaps": hook_gaps, "hook_gap_fills": hook_gap_fills,
            "analyzer_support": analyzer_support, "plan_gaps": plan_gaps}
