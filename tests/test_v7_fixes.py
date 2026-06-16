"""
Regression tests for v0.7.0 fixes:

1. deck-check no longer counts lands as ramp (basic lands matched "{T}: Add").
2. get_card_by_exact_name resolves double-faced cards by their front face.
3. `mtg card --json-output` emits structured JSON on a not-found card.
4. cards/prices/budget loaders accept a plain-text (.txt) decklist, not only JSON.
"""
import json
import pytest
from typer.testing import CliRunner

import mtgcli.cli as cli
from mtgcli.cli import app
from mtgcli.deckbuilder.deck_check import check_deck_quality
from mtgcli.utils.deck_io import load_deck_file

runner = CliRunner()


# ── Fix 1: lands are not ramp ────────────────────────────────────────────────

def _land(name, oracle):
    return {"name": name, "type_line": "Basic Land — Mountain", "oracle_text": oracle, "quantity": 1}


def test_basic_lands_not_counted_as_ramp():
    # 20 Mountains whose reminder text contains "{T}: Add {R}." used to match the
    # mana_rock phrase "{T}: Add" and inflate ramp. They must count only as lands.
    deck = [_land(f"Mountain{i}", "({T}: Add {R}.)") for i in range(20)]
    report = check_deck_quality(deck)
    assert report["stats"]["lands"] == 20
    assert report["stats"]["ramp"] == 0


def test_real_ramp_still_counts_with_lands_present():
    deck = [{"name": "Sol Ring", "type_line": "Artifact", "oracle_text": "{T}: Add {C}{C}.", "quantity": 1}]
    deck += [_land(f"Mountain{i}", "({T}: Add {R}.)") for i in range(35)]
    report = check_deck_quality(deck)
    assert report["stats"]["lands"] == 35
    assert report["stats"]["ramp"] == 1  # Sol Ring only, not the 35 Mountains


def test_true_ramp_land_counts_but_basics_do_not():
    # Root-cause fix: a land that actually ramps (searches a basic onto the
    # battlefield) counts as ramp; basics tapping for mana do not.
    ramp_land = {
        "name": "Myriad Landscape",
        "type_line": "Land",
        "oracle_text": "{T}, Sacrifice Myriad Landscape: Search your library for up to two basic land cards...",
        "quantity": 1,
    }
    deck = [ramp_land] + [_land(f"Mountain{i}", "({T}: Add {R}.)") for i in range(20)]
    report = check_deck_quality(deck)
    assert report["stats"]["lands"] == 21
    assert report["stats"]["ramp"] == 1  # only Myriad Landscape, not the 20 basics


# ── Fix 2: DFC front-face lookup ─────────────────────────────────────────────

def test_dfc_front_face_fallback():
    from mtgcli.cards.repository import CardRepository
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    repo = CardRepository(str(SQLITE_PATH))
    card = repo.get_card_by_exact_name("Valakut Awakening")
    if card is None:
        pytest.skip("Valakut Awakening not in this DB build")
    assert card["name"].startswith("Valakut Awakening")
    assert "//" in card["name"]


# ── Fix 3: card not-found emits JSON ─────────────────────────────────────────

def _patch_missing(monkeypatch):
    class FakePath:
        def exists(self): return True
        def __str__(self): return ":memory:"
    monkeypatch.setattr(cli, "SQLITE_PATH", FakePath())

    class FakeRepo:
        def __init__(self, *a, **k): pass
        def get_card_by_exact_name(self, _n): return None
        def search_cards_by_name(self, *a, **k): return [{"name": "Krenko, Mob Boss"}]
    monkeypatch.setattr(cli, "CardRepository", FakeRepo)


def test_card_not_found_json_is_parseable(monkeypatch):
    _patch_missing(monkeypatch)
    res = runner.invoke(app, ["card", "Krenkooo Typo", "--json-output"])
    # non-zero exit, but stdout must be valid JSON the agent can parse
    data = json.loads(res.stdout)
    assert data["found"] is False
    assert data["name"] == "Krenkooo Typo"
    assert "Krenko, Mob Boss" in data["suggestions"]


# ── Fix 4: loaders accept .txt decklists ─────────────────────────────────────

def test_load_deck_file_accepts_txt(tmp_path):
    txt = tmp_path / "list.txt"
    txt.write_text("1 Sol Ring\n2 Mountain\n# comment\n")
    result = load_deck_file(txt)
    names = {e["name"] for e in result["main_deck"]}
    assert "Sol Ring" in names
    assert "Mountain" in names


def test_load_deck_file_accepts_json(tmp_path):
    j = tmp_path / "deck.json"
    j.write_text(json.dumps({"commander": "Krenko, Mob Boss",
                             "main_deck": [{"name": "Sol Ring", "quantity": 1}]}))
    result = load_deck_file(j)
    assert result["commanders"] == ["Krenko, Mob Boss"]
    assert result["main_deck"][0]["name"] == "Sol Ring"


# ── Shared land-ramp guard (ramp_rules) across all three consumers ────────────

def _seed_tags():
    import json as _json
    from mtgcli.config import SEED_DATA_DIR
    return _json.loads((SEED_DATA_DIR / "card_tags.json").read_text())


def test_ramp_rules_basic_land_never_ramp_but_real_ramp_land_is():
    from mtgcli.deckbuilder.ramp_rules import land_matches_allowed_ramp_tags
    tags = _seed_tags()
    basic = {"name": "Mountain", "type_line": "Basic Land — Mountain", "oracle_text": "({T}: Add {R}.)"}
    fetch = {"name": "Evolving Wilds", "type_line": "Land",
             "oracle_text": "{T}, Sacrifice Evolving Wilds: Search your library for a basic land card..."}
    assert land_matches_allowed_ramp_tags(basic, tags) is False
    assert land_matches_allowed_ramp_tags(fetch, tags) is True


def test_search_by_tags_ramp_excludes_basic_lands():
    from mtgcli.cards.search import search_by_tags
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    results = search_by_tags(tags=["ramp"], limit=400)
    names = {c["name"] for c in results}
    assert not (names & {"Mountain", "Forest", "Island", "Swamp", "Plains"})


def test_search_by_tags_landfall_guard_inactive_keeps_lands():
    # landfall does not touch mana-production tags, so the land guard stays off and
    # land-matters results are not stripped.
    from mtgcli.cards.search import search_by_tags
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    results = search_by_tags(tags=["land_ramp"], limit=60)
    lands = [c for c in results if "land" in c.get("type_line", "").lower()]
    assert len(lands) > 0  # land_ramp search must still return ramp-lands


# ── enrich_deck accepts .txt like the other loaders ──────────────────────────

def test_enrich_deck_accepts_txt(tmp_path):
    from mtgcli.deckbuilder.enrich_deck import enrich_deck
    from mtgcli.config import SQLITE_PATH
    import json as _json
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    txt = tmp_path / "list.txt"
    txt.write_text("1 Sol Ring\n1 Goblin Rabblemaster\n")
    out = enrich_deck(txt, SQLITE_PATH, output_path=tmp_path / "enriched.json")
    enriched = _json.loads(out.read_text())
    by_name = {c["name"]: c for c in enriched}
    assert "Sol Ring" in by_name
    # enrichment pulled full card data, not just name/quantity
    assert by_name["Sol Ring"].get("type_line")


# ── deck-check vocabulary: fight-removal counted, board-wipe false positives gone ──

def test_deck_check_counts_fight_and_bite_as_removal():
    from mtgcli.deckbuilder.deck_check import check_deck_quality
    deck = [
        {"name": "Prey Upon", "type_line": "Sorcery",
         "oracle_text": "Target creature you control fights target creature you don't control.", "quantity": 1},
        {"name": "Rabid Bite", "type_line": "Sorcery",
         "oracle_text": "Target creature you control deals damage equal to its power to target creature you don't control.", "quantity": 1},
        {"name": "Ulvenwald Tracker", "type_line": "Creature — Human",
         "oracle_text": "{G}, {T}: Target creature you control fights target creature.", "quantity": 1},
    ]
    report = check_deck_quality(deck)
    assert report["stats"]["removal"] == 3  # all three are real green removal


def test_deck_check_board_wipe_no_false_positives():
    from mtgcli.deckbuilder.deck_check import check_deck_quality
    # Beneficial "each creature you control" / "all creatures able to block" effects
    # must NOT count as board wipes.
    benign = [
        {"name": "Shamanic Revelation", "type_line": "Sorcery",
         "oracle_text": "Draw a card for each creature you control.", "quantity": 1},
        {"name": "Nessian Boar", "type_line": "Creature — Boar",
         "oracle_text": "All creatures able to block Nessian Boar do so.", "quantity": 1},
    ]
    assert check_deck_quality(benign)["stats"]["board_wipe"] == 0


def test_deck_check_real_board_wipe_still_counts():
    from mtgcli.deckbuilder.deck_check import check_deck_quality
    wipes = [
        {"name": "Damnation", "type_line": "Sorcery", "oracle_text": "Destroy all creatures. They can't be regenerated.", "quantity": 1},
        {"name": "Toxic Deluge", "type_line": "Sorcery", "oracle_text": "All creatures get -X/-X until end of turn.", "quantity": 1},
    ]
    assert check_deck_quality(wipes)["stats"]["board_wipe"] == 2


# ── Archetype fit: creature-size bump (#3), fallback (#2), targeted-payoff (#7) ──

def test_score_archetype_fit_big_creature_bump():
    from mtgcli.category_counts.scoring import score_archetype_fit
    base = score_archetype_fit("Vigilance", "Legendary Creature — Hydra", "stompy")
    bumped = score_archetype_fit("Vigilance", "Legendary Creature — Hydra", "stompy", power=8)
    assert bumped > base               # an 8-power body reads as stompy
    assert bumped >= 4.0               # enough to avoid a forced-archetype warning
    # P/T omitted => unchanged (keeps existing callers/tests stable)
    assert score_archetype_fit("Vigilance", "Legendary Creature — Hydra", "stompy") == base


def test_score_archetype_fit_bump_only_for_beaters():
    from mtgcli.category_counts.scoring import score_archetype_fit
    # spellslinger is not a beatdown archetype: a big body must NOT inflate its fit
    no_pt = score_archetype_fit("", "Legendary Creature — Human", "spellslinger")
    with_pt = score_archetype_fit("", "Legendary Creature — Human", "spellslinger", power=8)
    assert with_pt == no_pt


def test_archetype_fit_never_empty_for_creature_commander():
    from mtgcli.deckbuilder.commander_analyzer import analyze_commander
    vanilla = {
        "name": "Big Dumb Beater", "can_be_commander": True, "commander_legal": True,
        "type_line": "Legendary Creature — Beast", "oracle_text": "Trample",
        "mana_value": 6, "color_identity": ["G"], "power": "9", "toughness": "9",
    }
    result = analyze_commander(vanilla)
    assert len(result["archetype_fit"]) > 0          # #2: fallback fills it
    assert len(result["build_direction_options"]) > 0


def test_targeted_spell_payoff_detected():
    from mtgcli.deckbuilder.commander_analyzer import analyze_commander
    gargos_like = {
        "name": "Gargos-like", "can_be_commander": True, "commander_legal": True,
        "type_line": "Legendary Creature — Hydra",
        "oracle_text": ("Vigilance. Whenever a creature you control becomes the target of a spell, "
                        "this creature fights up to one target creature you don't control."),
        "mana_value": 6, "color_identity": ["G"], "power": "8", "toughness": "7",
    }
    result = analyze_commander(gargos_like)
    assert "targeted_spell_payoff" in result["synergy_tags"]
    wanted = " ".join(result["wanted_card_patterns"]).lower()
    assert "target your own creatures" in wanted or "buyback" in wanted
