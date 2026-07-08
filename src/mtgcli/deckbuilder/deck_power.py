"""deck-power: the two categorizers (user design, 2026-07-06).

1. BRACKET COMPLIANCE — deterministic, rule-based (like singleton): the official
   Commander Brackets criteria approximated from deck contents: Game Changers count
   (the ingested WotC flag), mass land denial, extra-turn cards, complete 2-card
   infinite/auto-win combos, tutor density (informational). For users who WANT the
   official social contract; `n/a` users simply don't run it.

2. TIER — a heuristic efficiency score (0.0–10.0, bands of 0.5): synergy density +
   combos (classed) + game changers. CONSIDER-ONLY, never a gate. The philosophy
   (user's): synergy/combos/efficiency make decks strong — a pile of game changers
   without a plan stays low; without combos a deck caps around +C by design.

Combo sources: the external fetch (graceful degrade offline) + the agent's building
notes (`mtg note --type combo`), deduped by card set.

Calibration honesty (n=4 real builds): synergy density measured 0.25–0.43 on the
four finished decks; density reads TEXT-VISIBLE plan service only — commander-granted
synergy (Ragost's rocks-are-Foods) is invisible to card text and underreads.
"""
import re
from typing import Any, Dict, List, Optional, Set

from mtgcli.utils.phrase_match import any_phrase_matches

# ── tier bands (user spec: 0.5 steps, F below 5.0) ────────────────────────────
_TIER_BANDS = [
    (9.5, "+S"), (9.0, "S"), (8.5, "+A"), (8.0, "A"), (7.5, "+B"), (7.0, "B"),
    (6.5, "+C"), (6.0, "C"), (5.5, "+D"), (5.0, "D"),
]

# Combo class weights (auto-win > infinite > non-infinite > utility).
_COMBO_POINTS = {"auto_win": 1.25, "infinite": 0.75, "non_infinite": 0.4, "utility": 0.2}
_SYNERGY_SCALE = 14.5   # density 0.45 (top of the observed real-build band) ≈ 6.5
_SYNERGY_CAP = 6.5
_COMBO_CAP = 2.5
_GC_POINTS_EACH = 0.25
_GC_CAP = 1.0

# Mass land denial — documented approximation of the official criterion.
_MLD_PHRASES = [
    "destroy all lands", "destroy all artifacts, creatures, and lands",
    "sacrifices all lands", "destroy all nonbasic lands", "each player sacrifices a land",
    "return all lands",
]
_EXTRA_TURN_PHRASES = ["take an extra turn", "takes an extra turn after this one"]


def tier_band(score: float) -> str:
    for floor, band in _TIER_BANDS:
        if score >= floor:
            return band
    return "F"


def _card_text(card: Dict[str, Any]) -> str:
    return " ".join([card.get("name", "") or "", card.get("type_line", "") or "",
                     card.get("oracle_text", "") or ""]).lower()


# A land-fetch "tutor" (Cultivate, Farseek, Nature's Lore, Scapeshift, Realms Uncharted,
# Crop Rotation, Expedition Map) is RAMP/fixing, not a wincon tutor: its library search
# targets only lands. Excluding it stops green ramp from reading as tutor-dense (the
# tutor count conflates the two otherwise). A clause naming a nonland card type is a real
# tutor and is kept (Demonic/Vampiric, Green Sun's Zenith, Chord, Natural Order, Finale).
_LAND_SEARCH_RE = re.compile(r"search(?:es)? (?:your|their) library for ([^.,;\n]{0,90})")
_TUTOR_NONLAND_TYPES = ("creature", "artifact", "enchantment", "instant", "sorcery",
                        "planeswalker")
_TUTOR_LAND_WORDS = ("land", "forest", "island", "swamp", "mountain", "plains",
                     "gate", "desert", "wastes")


def _searches_only_land(text: str) -> bool:
    """True when the card's library-search clauses target ONLY lands (ramp/fixing),
    so it should not count as a wincon tutor. If any clause names a nonland card type
    it is a real tutor -> False."""
    matched_land = False
    for m in _LAND_SEARCH_RE.finditer(text):
        obj = m.group(1)
        if any(t in obj for t in _TUTOR_NONLAND_TYPES):
            return False
        if any(w in obj for w in _TUTOR_LAND_WORDS):
            matched_land = True
    return matched_land


# Impulse / dig / explore FALSE POSITIVES: "reveal the top card ... put that card into
# your hand" gives you a FORCED, non-chosen card (Coiling Oracle, Nissa Resurgent Animist,
# the Explore creatures, Dark Confidant, Ad Nauseam, Necropotence...). The 'put that card
# into your hand' tutor phrase catches these, over-reading consistency on green/value decks.
# A REAL chosen-card tutor either searches the library, names/chooses the card, or digs and
# lets you keep it (Demonic Consultation -> "chosen name"; Tainted Pact -> "exiled this
# way"); those markers exempt the card. Measured on the DB: 74 impulse/dig FPs excluded,
# 0 chosen-card tutors lost (Demonic Consultation / Tainted Pact / Vampiric / Grim survive).
_TOP_REVEAL = ("top of your library", "reveal the top", "top card of your library",
               "from the top of your")
_TUTOR_CHOICE_MARKERS = ("search your library", "name a card", "names a card",
                         "card name", "chosen name", "named card", "exiled this way")


def _is_impulse_dig(text: str) -> bool:
    """True when a 'put that card into your hand' match comes from a FORCED top-of-library
    reveal with no card selection -> impulse/dig/explore, not a wincon tutor."""
    if "put that card into your hand" not in text:
        return False
    if any(k in text for k in _TUTOR_CHOICE_MARKERS):
        return False
    return any(k in text for k in _TOP_REVEAL)


def classify_fetched_combo(results: List[str]) -> str:
    """Map the external source's result strings onto the user's combo classes."""
    text = " ".join(results).lower()
    if "win the game" in text or "lose the game" in text:
        return "auto_win"
    if "infinite" in text:
        return "infinite"
    if "near-infinite" in text:
        return "infinite"
    return "utility" if not text.strip() else "non_infinite"


def cross_check_combos(fetched: List[Dict[str, Any]], noted: List[Dict[str, Any]],
                       deck_names: Set[str], commander_name: str) -> Dict[str, Any]:
    """Complete combos (all pieces in deck/commander) + near-misses (1 piece away),
    deduped by frozenset of card names across both sources (noted wins on class:
    the agent saw the combo in context)."""
    have = {n.lower() for n in deck_names} | {commander_name.lower()}
    seen: Dict[frozenset, Dict[str, Any]] = {}
    complete: List[Dict[str, Any]] = []
    near: List[Dict[str, Any]] = []

    def consider(cards: List[str], combo_class: str, source: str, note: str = ""):
        key = frozenset(c.lower() for c in cards)
        if key in seen:
            return
        missing = [c for c in cards if c.lower() not in have]
        entry = {"cards": cards, "class": combo_class, "source": source}
        if note:
            entry["note"] = note
        if not missing:
            seen[key] = entry
            complete.append(entry)
        elif len(missing) == 1:
            entry["missing"] = missing[0]
            seen[key] = entry
            near.append(entry)

    for n in noted:  # noted first: agent classification wins the dedup
        consider(n.get("cards", []), n.get("combo_class", "non_infinite"), "note",
                 n.get("text", ""))
    for c in fetched:
        consider(c.get("cards", []), classify_fetched_combo(c.get("results", [])),
                 "external", "; ".join(c.get("results", [])[:3]))
    return {"complete": complete, "near_misses": near}


def compute_tier(synergy_density: Optional[float], complete_combos: List[Dict[str, Any]],
                 gc_count: int) -> Dict[str, Any]:
    syn_pts = round(min(_SYNERGY_CAP, (synergy_density or 0.0) * _SYNERGY_SCALE), 2)
    combo_counts: Dict[str, int] = {}
    combo_pts_raw = 0.0
    for c in complete_combos:
        cls = c.get("class", "non_infinite")
        combo_counts[cls] = combo_counts.get(cls, 0) + 1
        combo_pts_raw += _COMBO_POINTS.get(cls, 0.4)
    combo_pts = round(min(_COMBO_CAP, combo_pts_raw), 2)
    gc_pts = round(min(_GC_CAP, gc_count * _GC_POINTS_EACH), 2)
    score = round(min(10.0, syn_pts + combo_pts + gc_pts), 2)
    return {
        "score": score,
        "band": tier_band(score),
        "components": {
            "synergy": {"density": synergy_density, "points": syn_pts,
                        "scale": f"min({_SYNERGY_CAP}, density × {_SYNERGY_SCALE})"},
            "combos": {"counts": combo_counts, "points": combo_pts,
                       "weights": _COMBO_POINTS, "cap": _COMBO_CAP},
            "game_changers": {"count": gc_count, "points": gc_pts,
                              "each": _GC_POINTS_EACH, "cap": _GC_CAP},
        },
        "notes": [
            "consider-only: a heuristic efficiency read, never a gate or a verdict",
            "no-combo decks cap around +C by design (combos/efficiency drive top tiers)",
            "synergy density sees TEXT-visible plan service only — commander-granted "
            "synergy (e.g. Ragost turning rocks into Foods) underreads",
            "calibrated against 4 real builds (density band 0.25–0.43); coarse on purpose",
        ],
    }


def bracket_compliance(deck_cards: List[Dict[str, Any]], complete_combos: List[Dict[str, Any]],
                       tag_defs: Dict[str, List[str]],
                       target: Optional[str] = None) -> Dict[str, Any]:
    """Deterministic checks against the official bracket criteria (approximation
    documented per criterion). Computes the MINIMUM bracket the deck qualifies for."""
    gcs = [c.get("name", "") for c in deck_cards if c.get("game_changer")]
    mld = [c.get("name", "") for c in deck_cards
           if any_phrase_matches(_MLD_PHRASES, _card_text(c))]
    extra_turns = [c.get("name", "") for c in deck_cards
                   if any_phrase_matches(_EXTRA_TURN_PHRASES, _card_text(c))]
    tutor_phrases = tag_defs.get("tutor", ["search your library for"])
    tutors = [c.get("name", "") for c in deck_cards
              if any_phrase_matches(tutor_phrases, _card_text(c))
              and "land" not in (c.get("type_line") or "").lower()
              and not _searches_only_land(_card_text(c))
              and not _is_impulse_dig(_card_text(c))]
    two_card = [c for c in complete_combos
                if len(c.get("cards", [])) <= 2 and c.get("class") in ("infinite", "auto_win")]

    reasons: List[str] = []
    if mld:
        reasons.append(f"mass land denial present ({', '.join(mld[:4])})")
    if two_card:
        reasons.append(f"{len(two_card)} two-card infinite/auto-win combo(s) present")
    if len(extra_turns) >= 3:
        reasons.append(f"{len(extra_turns)} extra-turn cards (chaining risk)")
    if len(gcs) > 3:
        reasons.append(f"{len(gcs)} game changers (>3)")

    if reasons:
        computed = "4-5"
    elif gcs:
        computed = "3"
        reasons.append(f"{len(gcs)} game changer(s) (≤3): bracket 3 minimum")
    else:
        computed = "1-2"

    result: Dict[str, Any] = {
        "game_changers": {"count": len(gcs), "cards": gcs},
        "mass_land_denial": mld,
        "extra_turn_cards": extra_turns,
        "tutors": {"count": len(tutors), "cards": tutors,
                   "note": "informational — bracket guidance says 'few tutors' at low brackets, no hard limit"},
        "two_card_combos": two_card,
        "computed_min_bracket": computed,
        "criteria_note": ("approximation of the official Commander Brackets criteria; "
                          "MLD/extra-turn detection is phrase-based and coarse"),
    }
    if target:
        order = {"1": 1, "2": 2, "3": 3, "4": 4, "5": 5}
        floor = {"1-2": 1, "3": 3, "4-5": 4}[computed]
        t = order.get(str(target))
        if t is not None:
            result["target_bracket"] = str(target)
            result["compliant"] = t >= floor
            result["reasons"] = reasons if t < floor else []
    return result


def draw_odds(k: int, deck_size: int, opening: int = 7) -> Optional[Dict[str, Any]]:
    """Exact hypergeometric draw odds for k 'hit' cards in a deck of deck_size.

    The user's framing (2026-07-06): probabilities are interpretable where raw
    density is not — '92% chance your opening hand has a plan card' means something
    at the table. Representation, not new information: k is still the text-visible
    census. The commander is NOT drawable (command zone) and must be excluded from
    k by the caller.
    """
    from math import comb
    if deck_size <= 0 or k < 0 or k > deck_size:
        return None
    n = min(opening, deck_size)
    p_none_opening = comb(deck_size - k, n) / comb(deck_size, n) if k <= deck_size - n else 0.0
    return {
        "count": k,
        "deck_size": deck_size,
        "per_draw_pct": round(100 * k / deck_size, 1),
        "opening_at_least_one_pct": round(100 * (1 - p_none_opening), 1),
        "opening_expected": round(n * k / deck_size, 2),
    }
