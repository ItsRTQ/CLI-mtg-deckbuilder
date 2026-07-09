"""Consistency math — the tier engine (Consistency-engine Fase 3, user design).

TIER = deck consistency: "how fast and reliably do I reach my good cards and my
wincon?" All probabilities are EXACT hypergeometrics over the deck the agent
annotated (purposes on Cards, combos on the Deck); the only opinion lives in
data/seed/tier_weights.json (declared, tunable).

Structure (user-approved):
    CORE  = 10 × Q_wincon^w1 × P_bundle^w2 × (curve/10)^w3     (conjunctive)
    BONUS = arsenal (extra win routes) + raw GC count           (additive, capped)
    TIER  = min(10, CORE + BONUS) → 0.5 bands, F below 5.0

Refinements encoded:
  - Route QUALITY: reaching an auto-win infinite is stronger than reaching a value
    wincon (Toxrill-class). Q_wincon = 1 − Π(1 − P_route × strength_class).
  - Tutors (purpose SEARCH) act as WILDCARDS in combo assembly: each tutor seen
    covers one missing piece (exact two-group sum, not a heuristic).
  - Velocity multiplies everything through n_seen(T) instead of scoring separately
    (no double-dip).
Reliability guards: zero DECLARED win routes → tier None with a reason (never a
fake F for an unannotated deck); every component and constant is in the report.
"""
import json
from functools import lru_cache
from math import comb
from typing import Any, Dict, List

from mtgcli.config import SEED_DATA_DIR

_DEFAULTS: Dict[str, Any] = {
    "core_weights": {"wincon_access": 0.45, "function_bundle": 0.30, "curve": 0.25},
    "turn_targets": {"RAMP": 2, "DRAW": 3, "REMOVAL": 3, "SYNERGY": 4, "wincon_turn": 7},
    "route_strengths": {"auto_win": 1.0, "infinite": 0.85,
                        "wincon_single": 0.6, "non_infinite": 0.55},
    "velocity": {"draw_yield": 1.5},
    "bonus": {"arsenal_per_extra_route": 0.25, "arsenal_cap": 0.5,
              "gc_each": 0.125, "gc_cap": 0.5},
}


@lru_cache(maxsize=1)
def tier_weights() -> Dict[str, Any]:
    path = SEED_DATA_DIR / "tier_weights.json"
    if not path.exists():
        return _DEFAULTS
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _DEFAULTS
    merged = {}
    for key, default in _DEFAULTS.items():
        merged[key] = {**default, **{k: v for k, v in (data.get(key) or {}).items()
                                     if not k.startswith("_")}}
    return merged


# ── exact probability primitives ─────────────────────────────────────────────

def p_at_least_one(k: int, n_seen: int, deck_size: int) -> float:
    """P(≥1 of k hit-cards among n_seen drawn from deck_size). Exact."""
    if deck_size <= 0 or k <= 0:
        return 0.0
    n = min(int(n_seen), deck_size)
    if k >= deck_size:
        return 1.0
    if n <= 0:
        return 0.0
    if deck_size - k < n:
        return 1.0
    return 1.0 - comb(deck_size - k, n) / comb(deck_size, n)


def p_assemble(pieces: int, tutors: int, n_seen: int, deck_size: int) -> float:
    """P(assembling all `pieces` specific cards among n_seen, where each of the
    `tutors` SEARCH cards seen substitutes one missing piece). Exact two-group sum:
        P = Σ_{j,t: j+t≥pieces} C(k,j)·C(S,t)·C(N−k−S, n−j−t) / C(N,n)
    Pieces already in the command zone must be excluded by the caller (always
    available, not drawable)."""
    k, S, N = int(pieces), int(tutors), int(deck_size)
    n = min(int(n_seen), N)
    if k <= 0:
        return 1.0
    if N <= 0 or n <= 0 or k > N:
        return 0.0
    S = min(S, N - k)
    total = comb(N, n)
    hit = 0
    for j in range(0, min(k, n) + 1):
        need_t = max(0, k - j)
        for t in range(need_t, min(S, n - j) + 1):
            rest = n - j - t
            if rest < 0 or rest > N - k - S:
                continue
            hit += comb(k, j) * comb(S, t) * comb(N - k - S, rest)
    return min(1.0, hit / total)


def n_seen(turn: int, deck_size: int, k_draw: int, draw_yield: float) -> float:
    """Cards seen by `turn`: opening 7 + one draw per turn + velocity bonus
    (expected DRAW sources among the base cards × yield). Declared model."""
    base = 7 + max(0, int(turn))
    if deck_size > 0 and k_draw > 0:
        base += (min(base, deck_size) * k_draw / deck_size) * draw_yield
    return min(float(deck_size), base) if deck_size > 0 else float(base)


# ── the report ────────────────────────────────────────────────────────────────

def _band(score: float) -> str:
    from mtgcli.deckbuilder.deck_power import tier_band
    return tier_band(score)


def consistency_report(deck) -> Dict[str, Any]:
    """Full consistency report for a models.Deck. Returns tier None (with reason)
    when no win routes are DECLARED — never a fake F for an unannotated deck."""
    W = tier_weights()
    N = deck.size()
    purposes = deck.total_by_purpose()
    k_draw = purposes.get("DRAW", 0)
    k_search = purposes.get("SEARCH", 0)
    gc_count = purposes.get("GC", 0)
    commander_names = {c.name.lower() for c in deck.commanders}
    draw_yield = W["velocity"]["draw_yield"]

    if N == 0 or not purposes:
        return {"tier": None, "band": None,
                "reason": "deck has no annotated purposes yet — add Cards with purposes first"}

    # ── win routes: combos (classed) + single-card WINCONs ──────────────────
    t_win = W["turn_targets"]["wincon_turn"]
    seen_win = n_seen(t_win, N, k_draw, draw_yield)
    deck_names = {c.name.lower() for c in deck.cards}
    routes: List[Dict[str, Any]] = []
    broken_routes: List[Dict[str, Any]] = []
    for cls in ("auto_win", "infinite", "non_infinite"):
        for cb in deck.combos.get(cls, []):
            pieces = cb.get("cards_needed", [])
            # A piece that isn't in the deck (or the command zone) can never be drawn
            # OR tutored (tutors search YOUR library) — the route is unassemblable.
            # Report it as broken (the useful "one card away" signal) instead of
            # silently pretending it has odds (bug caught on the first live run:
            # Heliod+Ballista scored 0.296 with Ballista not in the deck).
            missing = [c for c in pieces
                       if c.lower() not in deck_names and c.lower() not in commander_names]
            if missing:
                broken_routes.append({"kind": cls, "cards": pieces, "missing": missing})
                continue
            drawable = [c for c in pieces if c.lower() not in commander_names]
            p = p_assemble(len(drawable), k_search, seen_win, N)
            routes.append({"kind": cls, "cards": pieces,
                           "pieces_drawable": len(drawable),
                           "p_assemble": round(p, 3),
                           "strength": W["route_strengths"].get(cls, 0.5)})
    combo_piece_names = {c.lower() for cls in ("auto_win", "infinite", "non_infinite")
                         for cb in deck.combos.get(cls, [])
                         for c in cb.get("cards_needed", [])}
    for card in deck.cards:
        if "WINCON" in card.purpose and card.name.lower() not in combo_piece_names:
            p = p_assemble(1, k_search, seen_win, N)
            routes.append({"kind": "wincon_single", "cards": [card.name],
                           "pieces_drawable": 1, "p_assemble": round(p, 3),
                           "strength": W["route_strengths"]["wincon_single"]})

    if not routes:
        return {"tier": None, "band": None,
                "reason": ("no ASSEMBLABLE win routes — annotate WINCON purposes or add "
                           "combos whose pieces are actually in the deck"),
                "broken_routes": broken_routes,
                "purposes": purposes}

    q_wincon = 1.0
    for r in routes:
        q_wincon *= (1.0 - r["p_assemble"] * r["strength"])
    q_wincon = 1.0 - q_wincon

    # ── function bundle at their target turns ────────────────────────────────
    bundle: Dict[str, Any] = {}
    probs = []
    for fn in ("RAMP", "DRAW", "REMOVAL", "SYNERGY"):
        turn = W["turn_targets"][fn]
        seen = n_seen(turn, N, k_draw, draw_yield)
        p = p_at_least_one(purposes.get(fn, 0), int(round(seen)), N)
        bundle[fn] = {"k": purposes.get(fn, 0), "turn": turn,
                      "n_seen": round(seen, 1), "p": round(p, 3)}
        probs.append(p)
    p_bundle = sum(probs) / len(probs)

    # ── curve ────────────────────────────────────────────────────────────────
    curve_score = deck.mana_curve_score()
    curve_component = (curve_score or 0.0) / 10.0

    # ── compose ─────────────────────────────────────────────────────────────
    cw = W["core_weights"]
    core = 10.0 * (q_wincon ** cw["wincon_access"]) \
                * (p_bundle ** cw["function_bundle"]) \
                * (curve_component ** cw["curve"]) if q_wincon > 0 and p_bundle > 0 \
                and curve_component > 0 else 0.0
    B = W["bonus"]
    arsenal = min(B["arsenal_cap"], B["arsenal_per_extra_route"] * max(0, len(routes) - 1))
    gc_bonus = min(B["gc_cap"], B["gc_each"] * gc_count)
    score = round(min(10.0, core + arsenal + gc_bonus), 2)

    return {
        "tier": score,
        "band": _band(score),
        "core": round(core, 2),
        "components": {
            "wincon_access": {"q": round(q_wincon, 3), "weight": cw["wincon_access"],
                              "turn": t_win, "n_seen": round(seen_win, 1),
                              "routes": routes, "broken_routes": broken_routes,
                              "tutors_as_wildcards": k_search},
            "function_bundle": {"p": round(p_bundle, 3), "weight": cw["function_bundle"],
                                "functions": bundle},
            "curve": {"score": curve_score, "weight": cw["curve"]},
            "bonus": {"arsenal": arsenal, "gc": gc_bonus, "gc_count": gc_count},
        },
        "notes": [
            "consider-only: exact probabilities over the AGENT'S annotation — a mislabeled deck lies (garbage-in declared)",
            "route strengths: reaching an auto-win infinite beats reaching a value wincon (Toxrill-class)",
            "independence across routes is a declared approximation (routes share draws)",
            "all constants live in data/seed/tier_weights.json",
        ],
    }
