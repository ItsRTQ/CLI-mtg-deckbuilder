"""RANK — deterministic POWER/speed meter for a Deck (FUEL-SPINE v1).

ORTHOGONAL to the consistency tier (models/consistency.py): the tier asks "how reliably
do I reach my good cards"; RANK asks "how fast/hard can this deck go". Thesis (user, backed
by the 24-deck calibration corpus in data/rank-calibration/NOTES.md): power = speed, and
fast_mana (rocks/rituals) is THE cEDH separator — the only axis with 0 false positives.
Tutors are a CAPPED secondary (consistency); draw is deliberately EXCLUDED (measured higher
in casual than cEDH — a grind signal the consistency tier already owns).

All constants are DECLARED JUDGMENT in data/seed/rank_weights.json (calibrated:false).
"""
import json
from functools import lru_cache
from typing import Any, Dict, List

from mtgcli.config import SEED_DATA_DIR
from mtgcli.deckbuilder.deck_power import _searches_only_land, _is_impulse_dig
from mtgcli.utils.phrase_match import any_phrase_matches


@lru_cache(maxsize=1)
def rank_weights() -> Dict[str, Any]:
    return json.loads((SEED_DATA_DIR / "rank_weights.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _tutor_phrases() -> tuple:
    tags = json.loads((SEED_DATA_DIR / "card_tags.json").read_text(encoding="utf-8"))
    return tuple(tags.get("tutor", ["search your library"]))


def _key(name: str) -> str:
    """Case-insensitive match key; DFC front-face only (matches the fast-mana list)."""
    return name.lower().split("//")[0].split("/")[0].strip()


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def compose_score(fast_mana: int, tutors: int, game_changers: int, free_interaction: int,
                  avg_mv_nonland: float, W: Dict[str, Any]) -> Dict[str, Any]:
    """The pure FUEL-SPINE math (no Deck dependency) → 0-10 score + component breakdown."""
    wt, den, cv = W["weights"], W["denominators"], W["curve"]
    fuel = min(1.0, fast_mana / den["fast_mana"])
    tut = min(1.0, tutors / den["tutors"])
    gc = min(1.0, game_changers / den["game_changers"])
    free = min(1.0, free_interaction / den["free_interaction"])
    curve = _clamp((cv["pivot"] - avg_mv_nonland) / cv["span"], 0.0, 1.0)
    composite = (wt["fuel"] * fuel + wt["tutor"] * tut + wt["game_changers"] * gc
                 + wt["curve"] * curve + wt["free_interaction"] * free)
    score = round(10.0 * composite, 2)
    return {
        "score": score,
        "components": {
            "fuel": {"raw": fast_mana, "unit": round(fuel, 3), "points": round(10 * wt["fuel"] * fuel, 2)},
            "tutor": {"raw": tutors, "unit": round(tut, 3), "points": round(10 * wt["tutor"] * tut, 2)},
            "game_changers": {"raw": game_changers, "unit": round(gc, 3), "points": round(10 * wt["game_changers"] * gc, 2)},
            "curve": {"raw": round(avg_mv_nonland, 2), "unit": round(curve, 3), "points": round(10 * wt["curve"] * curve, 2)},
            "free_interaction": {"raw": free_interaction, "unit": round(free, 3), "points": round(10 * wt["free_interaction"] * free, 2)},
        },
    }


def rank_band(score: float, W: Dict[str, Any]) -> Dict[str, Any]:
    """Map a 0-10 score onto the 7-band scale (thresholds on score/10)."""
    composite = score / 10.0
    for t in W["bands"]["thresholds"]:  # ordered high → low
        if composite >= t["min"]:
            return {"band": t["band"], "name": t["name"]}
    return {"band": 1, "name": "Scrap"}


def _metrics(deck, extra=()) -> Dict[str, Any]:
    W = rank_weights()
    fast_names = {_key(n) for n in W["fast_mana"]["names"]}
    free_names = {_key(n) for n in W["free_interaction"]["names"]}
    tutor_phrases = _tutor_phrases()
    fast = tut = gc = free = 0
    mv_sum = mv_n = 0
    tutor_cards: List[str] = []
    fast_cards: List[str] = []
    for c in list(deck._cards) + list(extra):
        q = c.quantity
        k = _key(c.name)
        if k in fast_names:
            fast += q
            fast_cards.append(c.name)
        if k in free_names:
            free += q
        if c.game_changer:
            gc += q
        tl = (c.type_line or "").lower()
        text = f"{c.name} {tl} {c.oracle_text}".lower()
        if "land" not in tl:
            mv_sum += (c.mana_value or 0) * q
            mv_n += q
        if (any_phrase_matches(tutor_phrases, text) and "land" not in tl
                and not _searches_only_land(text) and not _is_impulse_dig(text)):
            tut += q
            tutor_cards.append(c.name)
    # No nonland cards → no curve signal (don't let avg_mv=0 fake a perfect low curve).
    avg_mv = (mv_sum / mv_n) if mv_n else W["curve"]["pivot"]
    return {
        "fast_mana": fast, "tutors": tut, "game_changers": gc, "free_interaction": free,
        "avg_mv_nonland": round(avg_mv, 2),
        "fast_mana_cards": fast_cards, "tutor_cards": tutor_cards,
    }


def rank_report(deck, extra=()) -> Dict[str, Any]:
    """POWER rank for a deck: 0-10 FUEL-SPINE score + 7-band label + provenance.
    `extra` = extra Card objects to SIMULATE in the deck (upgrade what-if; the deck is
    not modified). Consider-only, ORTHOGONAL to the consistency tier. calibrated:false."""
    W = rank_weights()
    m = _metrics(deck, extra)
    scored = compose_score(m["fast_mana"], m["tutors"], m["game_changers"],
                           m["free_interaction"], m["avg_mv_nonland"], W)
    band = rank_band(scored["score"], W)
    return {
        "score": scored["score"],
        "band": band["band"],
        "band_name": band["name"],
        "metrics": {k: m[k] for k in ("fast_mana", "tutors", "game_changers",
                                      "free_interaction", "avg_mv_nonland")},
        "components": scored["components"],
        "cards": {"fast_mana": m["fast_mana_cards"], "tutors": m["tutor_cards"]},
        "calibrated": W.get("calibrated", False),
        "notes": [
            "consider-only: a deterministic POWER/speed estimate, not a verdict",
            "ORTHOGONAL to the consistency tier (Deck.tier) — power vs reliability",
            "fast_mana (rocks/rituals) is the spine; draw is excluded by design (grind, not speed)",
            "calibrated:false — mid bands (3-5) interpolated; all constants in rank_weights.json",
        ],
    }


def simulate_upgrades(deck, candidates) -> Dict[str, Any]:
    """Rank Upgrade Review helper: for each candidate Card, the EXACT marginal rank
    before→after if it were added (the deck is NOT modified — deterministic what-if).
    Also flags whether the candidate fits the commander's color identity, and gives the
    cumulative rank if ALL candidates were added. Powers the 'expected increase' the agent
    shows the user when steering toward a target rank band."""
    base = rank_report(deck)
    allowed = set()
    for c in deck.commanders:
        allowed |= set(c.color_identity)
    rows = []
    for card in candidates:
        after = rank_report(deck, extra=[card])
        rows.append({
            "name": card.name,
            "usd_price": card.usd_price,
            "legal_in_identity": set(card.color_identity) <= allowed,
            "rank_before": base["score"], "rank_after": after["score"],
            "rank_delta": round(after["score"] - base["score"], 2),
            "band_before": base["band"], "band_after": after["band"],
            "band_name_after": after["band_name"],
            "crosses_band": after["band"] > base["band"],
            "metrics_after": after["metrics"],
        })
    combined = rank_report(deck, extra=list(candidates)) if candidates else base
    return {
        "base": {"score": base["score"], "band": base["band"], "band_name": base["band_name"],
                 "metrics": base["metrics"]},
        "candidates": rows,
        "combined_rank": combined["score"],
        "combined_band": combined["band"],
        "combined_band_name": combined["band_name"],
        "combined_delta": round(combined["score"] - base["score"], 2),
    }
