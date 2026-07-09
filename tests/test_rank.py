"""Regression: Deck.rank() — the FUEL-SPINE power meter (calibrated:false).

Orthogonal to Deck.tier(): power/speed, not reliability. fast_mana (rocks/rituals) is the
spine; tutors capped secondary; draw excluded by design. Constants in rank_weights.json.
"""
import pytest

from mtgcli.models import Card, Deck
from mtgcli.models.rank import compose_score, rank_band, rank_weights


def _row(name, ident='["U","R"]', type_line="Artifact", mv=2.0, oracle="text", gc=0):
    return {
        "name": name, "mana_cost": "{2}", "mana_value": mv, "type_line": type_line,
        "oracle_text": oracle, "power": None, "toughness": None, "loyalty": None,
        "colors": ident, "color_identity": ident, "keywords": "[]",
        "produced_mana": None, "all_parts": None, "image_url": None,
        "edhrec_rank": 100, "usd_price": 1.0, "game_changer": gc,
    }


def _card(name, ident='["U","R"]', qty=1, **over):
    return Card(name, ["FLEX"], quantity=qty, db_row=_row(name, ident=ident, **over))


def _cmdr():
    return Card("Cmdr", ["WINCON"], db_row=_row("Cmdr", ident='["U","R"]',
                type_line="Legendary Creature"))


# ---------- pure math (pinned to the validated corpus) ----------

def test_compose_reproduces_dihada():
    # dihada corpus metrics (post tutor-fix): fast17 tut16 gc17 free1 avgmv2.05 → 9.55.
    W = rank_weights()
    s = compose_score(17, 16, 17, 1, 2.05, W)
    assert s["score"] == pytest.approx(9.55, abs=0.05)
    assert rank_band(s["score"], W)["band"] == 7  # Mythic


def test_compose_fuel_dominates_and_caps():
    W = rank_weights()
    # magda: 1 tutor but 13 fast → still Forbidden (fuel carries it, doesn't drop).
    magda = compose_score(13, 1, 6, 3, 2.27, W)
    assert magda["score"] == pytest.approx(7.34, abs=0.1)
    assert rank_band(magda["score"], W)["band"] == 6
    # fuel unit caps at 1.0 (fast_mana beyond the denominator adds nothing).
    a = compose_score(12, 0, 0, 0, 3.5, W)["components"]["fuel"]["unit"]
    b = compose_score(30, 0, 0, 0, 3.5, W)["components"]["fuel"]["unit"]
    assert a == b == 1.0


def test_bands_ordered_high_to_low():
    W = rank_weights()
    assert rank_band(9.0, W)["name"] == "Mythic"
    assert rank_band(7.7, W)["name"] == "Forbidden"
    assert rank_band(4.5, W)["name"] == "Charged"
    assert rank_band(0.6, W)["name"] == "Scrap"


# ---------- Deck.rank() end-to-end ----------

def test_deck_rank_reads_facts_no_annotation():
    d = Deck(_cmdr())
    d.add([
        _card("Sol Ring", oracle="{T}: Add {C}{C}."),          # fast_mana
        _card("Mana Vault", oracle="{T}: Add {C}{C}{C}."),      # fast_mana
        _card("Dark Ritual", type_line="Instant", oracle="Add {B}{B}{B}."),  # fast_mana
        _card("Demonic Tutor", type_line="Sorcery",
              oracle="Search your library for a card, put that card into your hand."),  # tutor
        _card("Coiling Oracle", type_line="Creature",
              oracle="Reveal the top card of your library. Otherwise, put that card "
              "into your hand."),                               # impulse -> NOT tutor
        _card("The One Ring", gc=1, oracle="Draw a card for each burden counter."),  # GC
    ])
    r = d.rank()
    assert r["metrics"]["fast_mana"] == 3
    assert r["metrics"]["tutors"] == 1           # Coiling Oracle excluded
    assert r["metrics"]["game_changers"] == 1
    assert 0.0 <= r["score"] <= 10.0
    assert r["band"] in range(1, 8)
    assert r["calibrated"] is False
    assert "Demonic Tutor" in r["cards"]["tutors"]
    assert "Coiling Oracle" not in r["cards"]["tutors"]


def test_deck_rank_empty_is_scrap():
    r = Deck(_cmdr()).rank()
    assert r["score"] == 0.0
    assert r["band"] == 1


def test_simulate_upgrades_marginal_delta_and_identity():
    from mtgcli.models.rank import simulate_upgrades
    d = Deck(_cmdr())  # UR commander
    d.add([_card("Sol Ring", oracle="{T}: Add {C}{C}.")])
    crypt = _card("Mana Crypt", ident='[]', oracle="{T}: Add {C}{C}.")   # fast mana, colorless
    birds = _card("Birds of Paradise", ident='["G"]', type_line="Creature",
                  oracle="{T}: Add one mana of any color.")              # off UR identity
    sim = simulate_upgrades(d, [crypt, birds])
    rows = {r["name"]: r for r in sim["candidates"]}
    assert rows["Mana Crypt"]["rank_delta"] > 0          # fast mana raises the rank
    assert rows["Mana Crypt"]["legal_in_identity"] is True
    assert rows["Birds of Paradise"]["legal_in_identity"] is False  # green off UR
    assert rows["Mana Crypt"]["rank_before"] == sim["base"]["score"]
    assert sim["combined_delta"] >= rows["Mana Crypt"]["rank_delta"]  # cumulative >= single
    # the deck itself was NOT modified by the simulation
    assert d.rank()["score"] == sim["base"]["score"]
