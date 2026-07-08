"""Regression: the two categorizers (deck-power) + building notes (user design).

- BRACKET compliance: deterministic official-criteria checks (GC count, MLD,
  extra turns, 2-card infinite/auto-win combos; tutors informational).
- TIER: 0.0-10.0 heuristic (synergy + combos + game changers), bands of 0.5,
  F below 5.0 — CONSIDER-ONLY by contract.
- `mtg note`: the carpenter's tally; combo notes feed deck-power; ghost card
  names warn (the bad-separator trap caught on first live use).
"""
import json

import pytest
from typer.testing import CliRunner

from mtgcli.cli import app
from mtgcli.deckbuilder.build_notes import add_note, combo_notes, load_notes, save_notes
from mtgcli.deckbuilder.deck_power import (
    bracket_compliance, classify_fetched_combo, compute_tier, cross_check_combos,
    tier_band, _searches_only_land, _is_impulse_dig,
)

runner = CliRunner()


# ---------- tier bands (user spec: 0.5 steps, F < 5.0) ----------

def test_tier_bands_user_spec():
    assert tier_band(9.5) == "+S"
    assert tier_band(9.4) == "S"
    assert tier_band(9.0) == "S"
    assert tier_band(8.9) == "+A"
    assert tier_band(8.0) == "A"
    assert tier_band(7.5) == "+B"
    assert tier_band(7.0) == "B"
    assert tier_band(6.5) == "+C"
    assert tier_band(6.0) == "C"
    assert tier_band(5.5) == "+D"
    assert tier_band(5.0) == "D"
    assert tier_band(4.99) == "F"
    assert tier_band(0.0) == "F"


def test_tier_formula_user_philosophy():
    # a pile of game changers WITHOUT synergy stays low (the user's thesis)
    gc_pile = compute_tier(synergy_density=0.05, complete_combos=[], gc_count=20)
    assert gc_pile["band"] == "F"
    # a no-combo synergy deck caps around +C by design
    tight = compute_tier(synergy_density=0.60, complete_combos=[], gc_count=0)
    assert tight["score"] <= 6.5
    # combos + synergy + GCs push top tiers
    combos = [{"class": "auto_win"}, {"class": "infinite"}, {"class": "infinite"}]
    strong = compute_tier(synergy_density=0.45, complete_combos=combos, gc_count=4)
    assert strong["band"] in ("S", "+S", "+A", "A")
    assert any("consider-only" in n for n in strong["notes"])


def test_classify_fetched_combo():
    assert classify_fetched_combo(["Win the game"]) == "auto_win"
    assert classify_fetched_combo(["Infinite mana", "Infinite storm count"]) == "infinite"
    assert classify_fetched_combo(["Draw a card"]) == "non_infinite"


# ---------- combo cross-check ----------

def test_cross_check_complete_near_and_dedup():
    deck = {"Heliod, Sun-Crowned", "Walking Ballista", "Sol Ring", "Aetherflux Reservoir"}
    fetched = [
        {"cards": ["Heliod, Sun-Crowned", "Walking Ballista"], "results": ["Win the game"]},
        {"cards": ["Karn, the Great Creator", "Mycosynth Lattice"], "results": ["Lock"]},
        {"cards": ["Aetherflux Reservoir", "Sol Ring"], "results": ["Infinite life loss"]},
    ]
    noted = [{"cards": ["Heliod, Sun-Crowned", "Walking Ballista"],
              "combo_class": "auto_win", "text": "seen in build"}]
    out = cross_check_combos(fetched, noted, deck, "Commander X")
    # noted wins the dedup (same card set as fetched #1)
    assert len(out["complete"]) == 2
    heliod = next(c for c in out["complete"] if "Heliod, Sun-Crowned" in c["cards"])
    assert heliod["source"] == "note" and heliod["class"] == "auto_win"
    # Karn combo: 2 pieces missing -> dropped entirely (not a near-miss)
    assert all("Karn, the Great Creator" not in c.get("cards", []) for c in out["near_misses"])


def test_cross_check_commander_counts_as_present():
    out = cross_check_combos(
        [{"cards": ["Commander X", "Sol Ring"], "results": ["Infinite mana"]}],
        [], {"Sol Ring"}, "Commander X")
    assert len(out["complete"]) == 1


# ---------- bracket compliance ----------

def _c(name, oracle="", type_line="Creature", gc=False):
    return {"name": name, "oracle_text": oracle, "type_line": type_line,
            "game_changer": gc, "quantity": 1}


def test_bracket_clean_deck_is_1_2():
    b = bracket_compliance([_c("Nice Guy")], [], {}, target="2")
    assert b["computed_min_bracket"] == "1-2"
    assert b["compliant"] is True


def test_bracket_gc_within_three_is_3():
    deck = [_c("Rhystic", gc=True), _c("Tithe", gc=True)]
    b = bracket_compliance(deck, [], {}, target="2")
    assert b["computed_min_bracket"] == "3"
    assert b["compliant"] is False and b["reasons"]


def test_bracket_mld_and_two_card_combo_push_4_5():
    deck = [_c("Armageddon", oracle="Destroy all lands.")]
    b = bracket_compliance(deck, [], {})
    assert b["computed_min_bracket"] == "4-5"
    b2 = bracket_compliance([_c("A")], [{"cards": ["X", "Y"], "class": "infinite"}], {})
    assert b2["computed_min_bracket"] == "4-5"


def test_bracket_four_gcs_push_4_5():
    deck = [_c(f"GC{i}", gc=True) for i in range(4)]
    assert bracket_compliance(deck, [], {})["computed_min_bracket"] == "4-5"


def test_searches_only_land_excludes_land_ramp():
    # Land-ramp / fixing: search targets ONLY lands -> not a wincon tutor.
    for txt in ("cultivate search your library for up to two basic land cards, reveal",
                "farseek search your library for a plains, island, swamp, or mountain card",
                "nature's lore search your library for a forest card and put it onto the battlefield",
                "crop rotation sacrifice a land: search your library for a land card"):
        assert _searches_only_land(txt) is True, txt
    # Real tutors: search names a nonland card type or a generic card -> kept.
    for txt in ("demonic tutor search your library for a card, then shuffle",
                "green sun's zenith search your library for a green creature card",
                "chord of calling search your library for a creature card"):
        assert _searches_only_land(txt) is False, txt


def test_tutor_count_excludes_land_only_search():
    tutor_tags = {"tutor": ["search your library"]}
    deck = [
        _c("Demonic Tutor", oracle="Search your library for a card, then shuffle.",
           type_line="Sorcery"),
        _c("Cultivate", oracle="Search your library for up to two basic land cards, reveal "
           "those cards, put one onto the battlefield tapped and the other into your hand.",
           type_line="Sorcery"),
        _c("Sol Ring", oracle="{T}: Add {C}{C}.", type_line="Artifact"),
    ]
    b = bracket_compliance(deck, [], tutor_tags)
    assert b["tutors"]["count"] == 1
    assert b["tutors"]["cards"] == ["Demonic Tutor"]


def test_is_impulse_dig_excludes_forced_reveal():
    # Forced top-of-library reveal, no card selection -> impulse/dig, NOT a tutor.
    for txt in (
        "coiling oracle reveal the top card of your library. if it's a land card, put "
        "it onto the battlefield. otherwise, put that card into your hand.",
        "nissa reveal cards from the top of your library until you reveal an elf or "
        "elemental card. put that card into your hand and the rest on the bottom.",
        "hermit druid reveal cards from the top of your library until you reveal a basic "
        "land card. put that card into your hand.",
    ):
        assert _is_impulse_dig(txt) is True, txt
    # Chosen-card digs ARE real tutors: you name/choose or keep-from-exile.
    for txt in (
        "demonic consultation choose a card name. exile the top six cards of your "
        "library, then reveal cards from the top of your library until you reveal a card "
        "with the chosen name. put that card into your hand.",
        "tainted pact exile the top card of your library. you may put that card into your "
        "hand unless it has the same name as another card exiled this way.",
        "vampiric tutor search your library for a card, then put that card on top.",
    ):
        assert _is_impulse_dig(txt) is False, txt


def test_tutor_count_excludes_impulse_dig():
    tutor_tags = {"tutor": ["search your library", "put that card into your hand",
                            "reveal it"]}
    deck = [
        _c("Demonic Consultation", type_line="Instant",
           oracle="Choose a card name. Exile the top six cards of your library, then "
           "reveal cards from the top of your library until you reveal a card with the "
           "chosen name. Put that card into your hand and exile the rest."),
        _c("Coiling Oracle",
           oracle="When this enters, reveal the top card of your library. If it's a land "
           "card, put it onto the battlefield. Otherwise, put that card into your hand."),
        _c("Nissa, Resurgent Animist", type_line="Legendary Creature",
           oracle="Reveal cards from the top of your library until you reveal an Elf or "
           "Elemental card. Put that card into your hand and the rest on the bottom."),
    ]
    b = bracket_compliance(deck, [], tutor_tags)
    assert b["tutors"]["count"] == 1
    assert b["tutors"]["cards"] == ["Demonic Consultation"]


# ---------- build notes ----------

def test_notes_roundtrip_and_combo_filter(tmp_path):
    p = tmp_path / "notes.json"
    add_note("saw a combo", note_type="combo", cards=["A", "B"],
             combo_class="infinite", path=p)
    add_note("a decision", note_type="decision", path=p)
    notes = load_notes(p)
    assert len(notes) == 2 and notes[0]["seq"] == 1 and notes[1]["seq"] == 2
    combos = combo_notes(p)
    assert len(combos) == 1 and combos[0]["combo_class"] == "infinite"
    save_notes([], p)
    assert load_notes(p) == []


def test_note_cli_validation():
    res = runner.invoke(app, ["note", "--json-output"])
    assert res.exit_code != 0
    assert json.loads(res.output)["error"]["type"] == "validation"
    res = runner.invoke(app, ["note", "combo without class", "--type", "combo",
                              "--json-output"])
    assert res.exit_code != 0
    assert json.loads(res.output)["error"]["type"] == "validation"


# ---------- draw odds (exact hypergeometric, user framing) ----------

def test_draw_odds_exact_hypergeometric():
    from math import comb
    from mtgcli.deckbuilder.deck_power import draw_odds
    o = draw_odds(18, 99)
    assert o["per_draw_pct"] == round(100 * 18 / 99, 1)
    expected_none = comb(81, 7) / comb(99, 7)
    assert o["opening_at_least_one_pct"] == round(100 * (1 - expected_none), 1)
    assert o["opening_expected"] == round(7 * 18 / 99, 2)


def test_draw_odds_edges():
    from mtgcli.deckbuilder.deck_power import draw_odds
    assert draw_odds(0, 99)["opening_at_least_one_pct"] == 0.0
    assert draw_odds(99, 99)["opening_at_least_one_pct"] == 100.0
    assert draw_odds(-1, 99) is None
    assert draw_odds(5, 0) is None
    # tiny decks: opening capped at deck size
    assert draw_odds(2, 3)["opening_expected"] == round(3 * 2 / 3, 2)
