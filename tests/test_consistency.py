"""Regression: the consistency tier engine (Fase 3, user design).

Exact math pinned by hand; the CORE is a weighted GEOMETRIC mean (consistency is
conjunctive — no wincon access = F, regardless of everything else); route QUALITY
weights the access (auto-win infinite > value wincon); tutors are exact wildcards
in assembly; broken routes (pieces not in deck) are reported, never scored (the
Ballista bug caught live); no declared routes -> tier None, never a fake F.
"""
from math import comb, isclose

import pytest

from mtgcli.models import Card, Deck
from mtgcli.models.consistency import (
    consistency_report, n_seen, p_assemble, p_at_least_one, tier_weights,
)


def _row(name, ident='[]', type_line="Artifact", mv=2.0, price=1.0, gc=0):
    return {"name": name, "mana_cost": "{2}", "mana_value": mv, "type_line": type_line,
            "oracle_text": "t", "power": None, "toughness": None, "loyalty": None,
            "colors": ident, "color_identity": ident, "keywords": "[]",
            "produced_mana": None, "all_parts": None, "image_url": None,
            "edhrec_rank": 1, "usd_price": price, "game_changer": gc}


def _card(name, purpose, qty=1, mv=2.0, type_line="Artifact", gc=0):
    return Card(name, purpose, quantity=qty,
                db_row=_row(name, type_line=type_line, mv=mv, gc=gc))


def _deck(cards=(), combos=()):
    d = Deck(Card("Cmd", ["WINCON"], db_row=_row("Cmd", type_line="Legendary Creature")))
    if cards:
        d.add(list(cards))
    for cls, pieces, how in combos:
        d.add_combo(cls, pieces, how)
    return d


# ---------- probability primitives (hand-pinned) ----------

def test_p_at_least_one_exact():
    assert isclose(p_at_least_one(18, 7, 99), 1 - comb(81, 7) / comb(99, 7))
    assert p_at_least_one(0, 7, 99) == 0.0
    assert p_at_least_one(99, 7, 99) == 1.0


def test_p_assemble_no_tutors_is_joint_hypergeometric():
    # both specific pieces among 10 seen of 40: C(38,8)/C(40,10) ... hand form:
    # P = C(2,2)*C(38,8)/C(40,10) + ... using the sum: j=2 (t=0)
    expected = comb(38, 8) / comb(40, 10)
    assert isclose(p_assemble(2, 0, 10, 40), expected, rel_tol=1e-9)


def test_p_assemble_tutors_raise_odds():
    base = p_assemble(2, 0, 10, 40)
    with_tutors = p_assemble(2, 4, 10, 40)
    assert with_tutors > base
    assert p_assemble(0, 0, 5, 40) == 1.0   # nothing to assemble
    assert p_assemble(3, 0, 0, 40) == 0.0   # nothing seen


def test_n_seen_velocity_bonus():
    plain = n_seen(5, 99, 0, 1.5)
    fueled = n_seen(5, 99, 10, 1.5)
    assert plain == 12
    assert fueled > plain
    assert n_seen(50, 30, 0, 1.5) == 30  # capped at deck size


# ---------- report semantics ----------

def _annotated_deck(with_combo=True, wincons=2):
    cards = [
        _card("Ramp1", ["RAMP"]), _card("Ramp2", ["RAMP"]),
        _card("Draw1", ["DRAW"]), _card("Draw2", ["DRAW"]),
        _card("Kill1", ["REMOVAL"]),
        _card("Syn1", ["SYNERGY"]), _card("Syn2", ["SYNERGY"]),
        _card("Tutor1", ["SEARCH"]),
        _card("PieceA", ["COMBO_PIECE"]), _card("PieceB", ["COMBO_PIECE"]),
        _card("Basic", ["FLEX"], qty=30, type_line="Basic Land — Wastes", mv=0.0),
    ]
    for i in range(wincons):
        cards.append(_card(f"Win{i}", ["WINCON"], mv=5.0))
    combos = [("auto_win", ["PieceA", "PieceB"], "loop")] if with_combo else []
    return _deck(cards, combos)


def test_report_structure_and_band():
    r = _annotated_deck().tier()
    assert r["tier"] is not None and r["band"] is not None
    comps = r["components"]
    assert 0 < comps["wincon_access"]["q"] <= 1
    assert comps["wincon_access"]["tutors_as_wildcards"] == 1
    assert set(comps["function_bundle"]["functions"]) == {"RAMP", "DRAW", "REMOVAL", "SYNERGY"}
    assert any("garbage-in" in n for n in r["notes"])


def test_no_routes_gives_none_never_fake_f():
    r = _annotated_deck(with_combo=False, wincons=0).tier()
    assert r["tier"] is None
    assert "win routes" in r["reason"]


def test_broken_route_reported_not_scored():
    d = _annotated_deck(with_combo=False, wincons=1)
    d.add_combo("auto_win", ["PieceA", "Ghost Piece"], "impossible")
    r = d.tier()
    broken = r["components"]["wincon_access"]["broken_routes"]
    assert len(broken) == 1 and broken[0]["missing"] == ["Ghost Piece"]
    assert all("Ghost Piece" not in rt["cards"]
               for rt in r["components"]["wincon_access"]["routes"])


def test_commander_piece_not_drawable_but_available():
    d = _annotated_deck(with_combo=False, wincons=1)
    d.add_combo("infinite", ["Cmd", "PieceA"], "with the commander")
    r = d.tier()
    route = next(rt for rt in r["components"]["wincon_access"]["routes"]
                 if rt["kind"] == "infinite")
    assert route["pieces_drawable"] == 1  # commander always available, not drawn


def test_route_quality_autowin_beats_value_wincon():
    strong = _deck([_card("W", ["WINCON"]), _card("P2", ["COMBO_PIECE"]),
                    _card("F", ["FLEX"], qty=30, type_line="Basic Land — Wastes", mv=0.0)],
                   [("auto_win", ["W", "P2"], "")])
    weak = _deck([_card("W", ["WINCON"]), _card("P2", ["COMBO_PIECE"]),
                  _card("F", ["FLEX"], qty=30, type_line="Basic Land — Wastes", mv=0.0)],
                 [("non_infinite", ["W", "P2"], "")])
    qs = strong.tier()["components"]["wincon_access"]["q"]
    qw = weak.tier()["components"]["wincon_access"]["q"]
    assert qs > qw  # same assembly odds, stronger class -> higher Q


def test_core_is_conjunctive_gc_pile_fails():
    # 20 GCs, no wincon routes -> tier None (no way to win declared);
    # with one weak wincon but zero ramp/draw/removal/synergy the core collapses
    d = _deck([_card(f"GC{i}", ["FLEX"], gc=1) for i in range(20)]
              + [_card("W", ["WINCON"], mv=9.0)])
    r = d.tier()
    assert r["tier"] is not None
    assert r["band"] == "F"  # user's thesis, structural: bundle p=0 -> core 0
    assert r["components"]["bonus"]["gc_count"] == 20
    assert r["components"]["bonus"]["gc"] == tier_weights()["bonus"]["gc_cap"]


def test_weights_seed_loads():
    w = tier_weights()
    assert isclose(sum(w["core_weights"].values()), 1.0)
    assert w["route_strengths"]["auto_win"] >= w["route_strengths"]["non_infinite"]
