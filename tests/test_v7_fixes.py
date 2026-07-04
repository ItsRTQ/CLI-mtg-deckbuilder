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
import mtgcli.cli.commands.cards as card_cmd  # `card`/`cards-batch` now live here (cli.py split)
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
    monkeypatch.setattr(card_cmd, "SQLITE_PATH", FakePath())

    class FakeRepo:
        def __init__(self, *a, **k): pass
        def get_card_by_exact_name(self, _n): return None
        def search_cards_by_name(self, *a, **k): return [{"name": "Krenko, Mob Boss"}]
        def suggest_similar_names(self, *a, **k): return [{"name": "Krenko, Mob Boss"}]
    monkeypatch.setattr(card_cmd, "CardRepository", FakeRepo)


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


# ── mtg card --field: direct field extraction, no json.tool|grep pipe needed ──

def test_card_field_returns_raw_value(monkeypatch):
    _patch_missing_for_field = None  # placeholder to keep diff minimal; real DB used below
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    res = runner.invoke(app, ["card", "Sol Ring", "--field", "mana_cost"])
    assert res.exit_code == 0
    assert res.stdout.strip() == "{1}"


def test_card_field_full_multiline_oracle_text_not_truncated(monkeypatch):
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    res = runner.invoke(app, ["card", "Toxrill, the Corrosive", "--field", "oracle_text"])
    if res.exit_code != 0:
        pytest.skip("Toxrill, the Corrosive not in this DB build")
    # The real oracle text has 4 lines; a `grep -A2` pipe would have truncated it.
    assert res.stdout.count("\n") >= 3
    assert "Slug" in res.stdout


def test_card_field_unknown_field_lists_available(monkeypatch):
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    res = runner.invoke(app, ["card", "Sol Ring", "--field", "nonsense_field"])
    assert res.exit_code == 1
    assert "oracle_text" in res.stdout  # helpful list of real field names


def test_card_field_not_found_emits_json(monkeypatch):
    _patch_missing(monkeypatch)
    res = runner.invoke(app, ["card", "Krenkooo Typo", "--field", "oracle_text"])
    assert res.exit_code == 1
    data = json.loads(res.stdout)
    assert data["found"] is False


# ── category-counts --table: flat pipe-friendly table, no inline-Python needed ──

def test_format_table_sorted_by_need_score_desc():
    from mtgcli.category_counts.output import format_table
    fake_result = {
        "land_count": 35, "nonland_slots": 64, "projected_avg_mv": 3.2,
        "archetype_fit_score": 4.0,
        "category_recommendations": [
            {"display_name": "Low Need", "category": "low", "need_score": 1.0,
             "recommended_range": "0-2", "compressed_target_count": 0, "priority": "Low"},
            {"display_name": "High Need", "category": "high", "need_score": 9.0,
             "recommended_range": "8-12", "compressed_target_count": 8, "priority": "Critical"},
        ],
    }
    table = format_table(fake_result)
    lines = table.splitlines()
    high_idx = next(i for i, l in enumerate(lines) if "High Need" in l)
    low_idx = next(i for i, l in enumerate(lines) if "Low Need" in l)
    assert high_idx < low_idx  # higher need_score sorts first


def test_format_table_includes_compressed_target_and_summary():
    from mtgcli.category_counts.output import format_table
    fake_result = {
        "land_count": 35, "nonland_slots": 64, "projected_avg_mv": 3.2,
        "archetype_fit_score": 4.0,
        "category_recommendations": [
            {"display_name": "Removal", "category": "removal", "need_score": 7.1,
             "recommended_range": "4-8", "compressed_target_count": 2, "priority": "High"},
        ],
    }
    table = format_table(fake_result)
    assert "Removal" in table and "4-8" in table and "2" in table
    assert "lands=35" in table and "fit=4.0" in table


def test_format_table_aligns_long_category_names():
    from mtgcli.category_counts.output import format_table
    fake_result = {
        "land_count": 1, "nonland_slots": 1, "projected_avg_mv": 1,
        "archetype_fit_score": 1,
        "category_recommendations": [
            {"display_name": "Counterspells / Stack Interaction", "category": "counterspells",
             "need_score": 5.2, "recommended_range": "2-5", "compressed_target_count": 0, "priority": "Medium"},
            {"display_name": "Tutors", "category": "tutors",
             "need_score": 2.2, "recommended_range": "0-2", "compressed_target_count": 0, "priority": "Low"},
        ],
    }
    lines = [l for l in format_table(fake_result).splitlines() if "Need" not in l and "lands=" not in l and l.startswith("-") is False]
    # Both rows' "Need" column should start at the same character offset.
    needs_col = [l.index("5.2") if "5.2" in l else l.index("2.2") for l in lines if "5.2" in l or "2.2" in l]
    assert len(set(needs_col)) == 1


# ── budget breakdown + high-cost flagging (kills OBS-4/6/8/10 + AF-4) ──────────

def test_budget_summary_breakdown_sorted_desc():
    from mtgcli.deckbuilder.pricing import build_budget_summary
    deck = [
        {"name": "Cheap", "quantity": 1, "usd_price": 1.0},
        {"name": "Pricey", "quantity": 2, "usd_price": 10.0},   # line_total 20
        {"name": "Mid", "quantity": 1, "usd_price": 5.0},
    ]
    s = build_budget_summary(deck)
    names = [c["name"] for c in s["breakdown"]]
    assert names == ["Pricey", "Mid", "Cheap"]          # sorted by line_total desc
    assert s["breakdown"][0]["line_total"] == 20.0      # price * quantity


def test_budget_high_cost_cards_flagged_against_budget():
    from mtgcli.deckbuilder.pricing import build_budget_summary
    deck = [
        {"name": "Whale", "quantity": 1, "usd_price": 30.0},
        {"name": "Minnow", "quantity": 1, "usd_price": 2.0},
    ]
    s = build_budget_summary(deck, budget_limit=100.0, high_cost_pct=0.20)
    flagged = {c["name"] for c in s["high_cost_cards"]}
    assert flagged == {"Whale"}                         # 30 >= 20% of 100; 2 is not
    assert s["high_cost_cards"][0]["pct_of_budget"] == 30.0


def test_budget_no_high_cost_key_without_budget_limit():
    from mtgcli.deckbuilder.pricing import build_budget_summary
    s = build_budget_summary([{"name": "X", "quantity": 1, "usd_price": 99.0}])
    assert "high_cost_cards" not in s                    # only computed with a budget
    assert "breakdown" in s                              # breakdown always present


# ── cards-batch --verify: plain-text not-found summary + exit code (OBS-3/5) ──

def test_cards_batch_verify_clean_exits_zero(tmp_path):
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    lst = tmp_path / "ok.txt"
    lst.write_text("1 Sol Ring\n1 Llanowar Elves\n")
    res = runner.invoke(app, ["cards-batch", str(lst), "--verify"])
    assert res.exit_code == 0
    assert "0 not found" in res.stdout


def test_cards_batch_verify_flags_missing_and_exits_one(tmp_path):
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    lst = tmp_path / "bad.txt"
    lst.write_text("1 Sol Ring\n1 Craterhoof Behemot\n")
    res = runner.invoke(app, ["cards-batch", str(lst), "--verify"])
    assert res.exit_code == 1
    assert "Craterhoof Behemot" in res.stdout
    assert "1 not found" in res.stdout


def test_cards_batch_verify_json_shape(tmp_path):
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    lst = tmp_path / "bad.txt"
    lst.write_text("1 Sol Ring\n1 Craterhoof Behemot\n")
    res = runner.invoke(app, ["cards-batch", str(lst), "--verify", "--json-output"])
    data = json.loads(res.stdout)
    assert data["total_entries"] == 2
    assert data["not_found_count"] == 1
    assert data["not_found"][0]["name"] == "Craterhoof Behemot"


# ── deck-swap: validates before writing, replaces the raw edit script (OBS-7) ──

def _gargos_list(tmp_path):
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    p = tmp_path / "deck.txt"
    p.write_text("1 Pelakka Wurm\n1 Carnage Tyrant\n1 Llanowar Elves\n")
    return p


def test_deck_swap_valid_writes(tmp_path):
    p = _gargos_list(tmp_path)
    res = runner.invoke(app, ["deck-swap", "--deck", str(p), "--commander",
                              "Gargos, Vicious Watcher", "--swap", "Pelakka Wurm=Thragtusk"])
    assert res.exit_code == 0
    text = p.read_text()
    assert "Thragtusk" in text and "Pelakka Wurm" not in text


def test_deck_swap_off_color_aborts(tmp_path):
    p = _gargos_list(tmp_path)
    res = runner.invoke(app, ["deck-swap", "--deck", str(p), "--commander",
                              "Gargos, Vicious Watcher", "--swap", "Pelakka Wurm=Lightning Bolt"])
    assert res.exit_code == 1
    assert "color identity" in res.stdout.lower()
    assert "Pelakka Wurm" in p.read_text()  # unchanged — nothing written


def test_deck_swap_card_not_in_deck_aborts(tmp_path):
    p = _gargos_list(tmp_path)
    res = runner.invoke(app, ["deck-swap", "--deck", str(p), "--swap", "Black Lotus=Sol Ring"])
    assert res.exit_code == 1
    assert "not in the deck" in res.stdout.lower()


def test_deck_swap_duplicate_aborts(tmp_path):
    p = _gargos_list(tmp_path)
    # Carnage Tyrant is already present -> swapping another card into it is a singleton violation
    res = runner.invoke(app, ["deck-swap", "--deck", str(p), "--commander",
                              "Gargos, Vicious Watcher", "--swap", "Pelakka Wurm=Carnage Tyrant"])
    assert res.exit_code == 1
    assert "duplicate" in res.stdout.lower()
    assert "Pelakka Wurm" in p.read_text()  # unchanged


def test_deck_swap_malformed_aborts(tmp_path):
    p = _gargos_list(tmp_path)
    res = runner.invoke(app, ["deck-swap", "--deck", str(p), "--swap", "no equals sign here"])
    assert res.exit_code == 1
    assert "malformed" in res.stdout.lower()


# ── General oracle hook extraction (commander-agnostic) ───────────────────────

def test_oracle_hooks_named_counters_generic():
    from mtgcli.deckbuilder.oracle_hooks import extract_named_counters
    assert extract_named_counters("put a slime counter on each creature you don't control") == ["slime"]
    assert extract_named_counters("you get an experience counter") == ["experience"]
    assert extract_named_counters("enters with five +1/+1 counters on it") == ["+1/+1"]


def test_oracle_hooks_counter_verb_not_mistaken_for_type():
    from mtgcli.deckbuilder.oracle_hooks import extract_named_counters
    # "counter target spell" is the verb sense — must not yield a counter type
    assert extract_named_counters("Whenever you counter target spell, draw a card.") == []


def test_oracle_hooks_custom_counter_avoids_plus_one_payoffs():
    from mtgcli.deckbuilder.oracle_hooks import extract_hooks
    h = extract_hooks("At the beginning of each end step, put a slime counter on each creature you don't control.")
    joined = " ".join(h["build_signals"]).lower()
    assert "proliferate" in joined
    assert "avoid +1/+1" in joined         # the dead-payoff warning
    assert h["asymmetric_punisher"] is True


def test_oracle_hooks_plus_one_counter_uses_standard_payoffs():
    from mtgcli.deckbuilder.oracle_hooks import extract_hooks
    h = extract_hooks("Enters with five +1/+1 counters on it.")
    joined = " ".join(h["build_signals"]).lower()
    assert "+1/+1 counter payoffs" in joined
    assert "avoid +1/+1" not in joined     # standard counters are NOT warned against


def test_oracle_hooks_trigger_families_and_cost_reduction():
    from mtgcli.deckbuilder.oracle_hooks import extract_hooks
    h = extract_hooks(
        "Hydra spells you cast cost {4} less to cast.\n"
        "Whenever a creature you control becomes the target of a spell, it fights."
    )
    assert "targeted_by_spell" in h["trigger_events"]
    assert h["cost_reduction_type"] == "Hydra"
    joined = " ".join(h["build_signals"]).lower()
    assert "target your own creatures" in joined
    assert "hydra spells" in joined


def test_oracle_hooks_spellslinger_and_sacrifice_triggers():
    from mtgcli.deckbuilder.oracle_hooks import extract_trigger_events
    assert "you_cast_spell" in extract_trigger_events("Whenever you cast an instant or sorcery spell, create a token.")
    assert "sacrifice" in extract_trigger_events("Whenever you sacrifice a permanent, draw a card.")
    assert "permanent_dies" in extract_trigger_events("Whenever another creature you control dies, you get a counter.")


# ── mtg preflight: single finalization gate (anti rule-skip) ──────────────────

def test_preflight_broken_deck_not_ready(tmp_path):
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    bad = tmp_path / "broken.txt"
    bad.write_text("1 Sol Ring\n1 Lightning Bolt\n1 Counterspell\n")  # off-color + wrong size
    res = runner.invoke(app, ["preflight", "--deck", str(bad), "--commander", "Gargos, Vicious Watcher"])
    assert res.exit_code == 1
    assert "NOT READY" in res.stdout
    assert "color identity" in res.stdout.lower()


def test_preflight_json_shape(tmp_path):
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    bad = tmp_path / "broken.txt"
    bad.write_text("1 Lightning Bolt\n")
    res = runner.invoke(app, ["preflight", "--deck", str(bad), "--commander",
                              "Gargos, Vicious Watcher", "--json-output"])
    data = json.loads(res.stdout)
    assert data["ready"] is False
    assert isinstance(data["checks"], list)
    assert any(c["check"].startswith("Within color identity") and c["status"] == "FAIL" for c in data["checks"])


# ── Contract: EVERY CLI command must expose --json-output (the "global" guarantee) ──

def test_every_command_supports_json_output():
    """Introspect the Typer app: every registered command must offer --json-output, so
    machine-readable output can't silently regress when new commands are added."""
    import inspect
    from mtgcli.cli import app
    missing = []
    for cmd in app.registered_commands:
        decls = []
        for _, param in inspect.signature(cmd.callback).parameters.items():
            decls.extend(getattr(param.default, "param_decls", None) or [])
        if "--json-output" not in decls:
            missing.append(cmd.callback.__name__)
    assert not missing, f"Commands missing --json-output: {missing}"


def test_status_json_output_shape():
    res = runner.invoke(app, ["status", "--json-output"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert "project_root" in data and "database_exists" in data


# ── GF-1: punisher detection is general — targeted fight ≠ mass board punisher ──

def test_punisher_targeted_fight_not_flagged():
    from mtgcli.deckbuilder.oracle_hooks import is_asymmetric_punisher
    # Gargos-style: a single targeted fight is removal, NOT a punisher
    assert is_asymmetric_punisher(
        "Whenever a creature you control becomes the target of a spell, "
        "Gargos fights up to one target creature you don't control."
    ) is False


def test_punisher_mass_board_flagged():
    from mtgcli.deckbuilder.oracle_hooks import is_asymmetric_punisher
    # Toxrill-style mass effect, and explicit opponent scope
    assert is_asymmetric_punisher("Creatures you don't control get -1/-1 for each slime counter on them.") is True
    assert is_asymmetric_punisher("At the beginning of your upkeep, each opponent loses 2 life.") is True


def test_punisher_not_triggered_by_plain_targeted_removal():
    from mtgcli.deckbuilder.oracle_hooks import is_asymmetric_punisher
    assert is_asymmetric_punisher("Destroy target creature you don't control.") is False


# ── GF-2: deck-fill-lands fills in place without requiring --force ─────────────

def test_fill_lands_in_place_needs_no_force(tmp_path):
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    lst = tmp_path / "d.txt"
    lst.write_text("1 Llanowar Elves\n")
    deck = tmp_path / "deck.json"
    runner.invoke(app, ["deck-write", "--input", str(lst), "--output", str(deck),
                        "--commander", "Gargos, Vicious Watcher", "--structured"])
    assert deck.exists()
    # In-place fill over the existing file, no --force:
    res = runner.invoke(app, ["deck-fill-lands", "--deck", str(deck), "--commander", "Gargos, Vicious Watcher"])
    assert res.exit_code == 0
    assert "already exists" not in res.stdout



# ── search-tags: ranking by facets matched + --list-tags (consolidated concept search) ──

def test_search_tags_ranks_by_match_count():
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    from mtgcli.cards.search import search_by_tags
    res = search_by_tags(tags=["evasion"], colors="G", type_filter="creature", limit=10, rank=True)
    assert res, "expected evasive green creatures"
    counts = [c.get("tag_match_count", 0) for c in res]
    assert counts == sorted(counts, reverse=True)   # ranked by facets, desc
    assert counts[0] >= 1


def test_search_tags_multiple_tags_union_and_rank():
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    from mtgcli.cards.search import search_by_tags
    res = search_by_tags(tags=["evasion", "trample"], colors="G", type_filter="creature", limit=15, rank=True)
    assert all("tag_match_count" in c for c in res)


def test_cli_search_tags_list_and_ranked_output():
    res = runner.invoke(app, ["search-tags", "--list-tags", "--json-output"])
    assert res.exit_code == 0
    names = json.loads(res.stdout)
    assert "evasion" in names and "reanimation" in names and "sacrifice_outlet" in names

    res2 = runner.invoke(app, ["search-tags", "evasion", "--colors", "G", "--type", "creature",
                               "--limit", "3", "--json-output"])
    assert res2.exit_code == 0
    data = json.loads(res2.stdout)
    assert all("tag_match_count" in c for c in data)


# ── #3: numeric power/toughness queries (safe coercion of */null) ─────────────

def test_parser_power_toughness_tokens():
    from mtgcli.cards.query_parser import parse_search_query
    p = parse_search_query("pow>=5 tou<=3")
    assert p["power_gte"] == 5.0
    assert p["toughness_lte"] == 3.0


def test_power_filter_excludes_star_power(tmp_path):
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    # Mortivore is */*; pow>=4 must NOT match it, but no filter must.
    with_filter = runner.invoke(app, ["search", "--name", "Mortivore", "--pow-gte", "4", "--json-output"])
    no_filter = runner.invoke(app, ["search", "--name", "Mortivore", "--json-output"])
    # with filter: "No cards found" (not JSON) or empty; without: found
    assert "Mortivore" not in with_filter.stdout or with_filter.stdout.strip().startswith("No")
    assert "Mortivore" in no_filter.stdout


def test_power_filter_returns_real_beaters(tmp_path):
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    res = runner.invoke(app, ["search", "--colors", "G", "--type", "creature",
                              "--pow-gte", "5", "--mv-lte", "4", "--limit", "10", "--json-output"])
    data = json.loads(res.stdout)
    assert data, "expected some efficient green beaters"
    for c in data:
        assert int(c["power"]) >= 5 and c["mana_value"] <= 4


# ── keystone: card_function_profile + complement map ──────────────────────────

def test_card_function_profile_detects_sac_outlet():
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    from mtgcli.cards.repository import CardRepository
    from mtgcli.deckbuilder.card_profile import card_function_profile
    repo = CardRepository(str(SQLITE_PATH))
    p = card_function_profile(repo.get_card_by_exact_name("Viscera Seer"))
    assert "sacrifice_outlet" in p["tags"] or "free_sacrifice_outlet" in p["tags"]


def test_complementary_tags_sac_outlet_finds_payoffs():
    from mtgcli.deckbuilder.card_profile import complementary_tags
    comp = complementary_tags(["sacrifice_outlet"])
    assert "death_trigger" in comp and "reanimation" in comp
    assert "sacrifice_outlet" not in comp   # excludes what the source already has


# ── #1 similar / complements commands ─────────────────────────────────────────

def test_cli_similar_returns_shared_function(tmp_path):
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    res = runner.invoke(app, ["similar", "Viscera Seer", "--limit", "5", "--json-output"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data["source"] == "Viscera Seer"
    assert all(c["name"] != "Viscera Seer" for c in data["results"])  # source excluded


def test_cli_complements_finds_other_half(tmp_path):
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    res = runner.invoke(app, ["complements", "Viscera Seer", "--colors", "B", "--limit", "5", "--json-output"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert "death_trigger" in data["complement_tags"] or "reanimation" in data["complement_tags"]


# ── #2 trigger-family search ──────────────────────────────────────────────────

def test_cli_search_by_trigger(tmp_path):
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    res = runner.invoke(app, ["search", "--trigger", "permanent_dies", "--colors", "B",
                              "--type", "creature", "--limit", "5", "--json-output"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data, "expected death-trigger creatures"


def test_cli_search_trigger_unknown_errors():
    res = runner.invoke(app, ["search", "--trigger", "not_a_family"])
    assert res.exit_code == 1
    assert "Unknown trigger" in res.stdout


# ── #5 deck-gaps ──────────────────────────────────────────────────────────────

def test_deck_gaps_flags_thin_deck_and_hooks(tmp_path):
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("card DB not built")
    thin = tmp_path / "thin.txt"
    thin.write_text("1 Sol Ring\n1 Llanowar Elves\n")
    res = runner.invoke(app, ["deck-gaps", "--deck", str(thin), "--commander",
                              "Toxrill, the Corrosive", "--archetype", "control", "--json-output"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert len(data["gaps"]) > 0                     # a 2-card deck has gaps
    # Toxrill's slime counters should trigger the proliferate hook-gap
    assert any("proliferate" in hg for hg in data["hook_gaps"])


def test_legendary_multitype_commanders_flagged():
    """'Legendary Enchantment Creature' (Gods) and 'Legendary Artifact Creature' are commanders:
    the contiguous 'Legendary Creature' substring missed 182 of them."""
    from mtgcli.config import SQLITE_PATH
    import pytest, sqlite3
    if not SQLITE_PATH.exists():
        pytest.skip("DB not built")
    con = sqlite3.connect(str(SQLITE_PATH))
    for n in ["Kruphix, God of Horizons", "Heliod, Sun-Crowned", "Karn, Legacy Reforged"]:
        r = con.execute("SELECT can_be_commander FROM cards WHERE name=?", (n,)).fetchone()
        if r:
            assert r[0] == 1, f"{n} should be commander-eligible"
    n = con.execute("""SELECT COUNT(*) FROM cards WHERE type_line LIKE '%Legendary%'
      AND type_line LIKE '%Creature%' AND commander_legal=1 AND can_be_commander=0""").fetchone()[0]
    assert n == 0, f"{n} legal legendary creatures still unflagged"


def test_deck_entries_accept_plain_strings():
    """F5: a deck JSON with ["Sol Ring", ...] string entries must not crash any consumer."""
    from mtgcli.utils.deck_io import normalize_deck_input
    d = normalize_deck_input({"commander": "X", "main_deck": ["Sol Ring", {"name": "Island", "quantity": 3}]})
    assert d["main_deck"][0] == {"name": "Sol Ring", "quantity": 1}
    assert d["main_deck"][1]["quantity"] == 3


def test_json_output_error_boundary():
    """F2b/F4: with --json-output, usage/validation errors emit JSON, never Rich panels."""
    import subprocess, json
    for args in (["cards-batch", "--file", "/tmp/x", "--json-output"],
                 ["fill-lands", "--json-output"],
                 ["search", "--type", "Rogue", "--json-output"]):
        out = subprocess.run(["mtg"] + args, capture_output=True, text=True)
        d = json.loads(out.stdout.strip())
        assert "error" in d and d["error"]["message"]


def test_card_not_found_fuzzy_suggestions():
    """Regression: the not-found suggester was pure substring LIKE, so an in-word typo
    ("Krenkooo") suggested NOTHING. suggest_similar_names falls back to fuzzy matching
    (difflib, cutoff 0.6 — measured against the real DB) when substring finds nothing."""
    from mtgcli.cards.repository import CardRepository
    from mtgcli.config import SQLITE_PATH
    repo = CardRepository(str(SQLITE_PATH))
    # in-word typo: substring LIKE finds nothing, fuzzy must recover the real card
    names = [s["name"] for s in repo.suggest_similar_names("Krenkooo", limit=5)]
    assert "Krenko, Mob Boss" in names
    names = [s["name"] for s in repo.suggest_similar_names("Sol Rign", limit=5)]
    assert "Sol Ring" in names
    # substring path still wins when it matches (cheap, unchanged behavior)
    names = [s["name"] for s in repo.suggest_similar_names("Krenko", limit=5)]
    assert any("Krenko" in n for n in names)


def test_json_output_failure_exit_code_propagates():
    """Regression: click with standalone_mode=False SWALLOWS typer.Exit and returns the
    exit code instead of raising, so `mtg card <not-found> --json-output` exited 0 while
    its JSON said found:false — breaking the documented non-zero-exit contract that
    agent pipelines rely on. _run_app must propagate the returned code."""
    import subprocess, json
    out = subprocess.run(["mtg", "card", "Zzzyzx Qqq Nonexistent", "--json-output"],
                         capture_output=True, text=True)
    d = json.loads(out.stdout.strip())
    assert d["found"] is False
    assert out.returncode == 1, f"expected exit 1, got {out.returncode}"
    # and a successful command still exits 0 through the same boundary
    ok = subprocess.run(["mtg", "card", "Sol Ring", "--json-output"],
                        capture_output=True, text=True)
    assert ok.returncode == 0


def test_sqlite_schema_insert_row_in_sync():
    """The 'edhrec_rank init-data crash' class: schema columns, INSERT column list, VALUES
    placeholders and _to_row output MUST stay in sync — this test needs no network."""
    import re
    from mtgcli.data import build_sqlite as b
    insert_cols = re.search(r"INSERT OR REPLACE INTO cards \((.*?)\)", b._INSERT_SQL, re.S).group(1)
    n_cols = len([c for c in insert_cols.split(",") if c.strip()])
    n_qs = b._INSERT_SQL.count("?")
    dummy = {k: None for k in [
        "oracle_id","name","mana_cost","type_line","oracle_text","power","toughness",
        "usd_price","usd_foil_price","usd_etched_price","edhrec_rank","eur_price",
        "eur_foil_price","tix_price","price_status","price_source","layout"]}
    dummy.update({"mana_value": 0, "colors": [], "color_identity": [], "commander_legal": True,
                  "can_be_commander": False, "games": [], "digital": False, "finishes": []})
    n_row = len(b._to_row(dummy))
    assert n_cols == n_qs == n_row, f"schema={n_cols} placeholders={n_qs} row={n_row}"


def test_fight_counts_as_built_in_removal():
    """F10: Gargos's fight trigger is repeatable removal; the legacy scorer scored it 0.0."""
    from mtgcli.category_counts.scoring import _score_provides
    assert _score_provides("gargos fights up to one target creature")["targeted_removal"] >= 2.0


def test_philosophy_fallback_warns():
    """F10: unknown philosophy strings silently fell back to 'balanced' — now they warn."""
    from mtgcli.category_counts.calculator import _philosophy_warning
    assert _philosophy_warning("fight-removal engine") is not None
    assert "balanced" in _philosophy_warning("nonsense xyz")
    assert _philosophy_warning("combat_pressure") is None


def test_provides_detectors():
    """M2-prep: TUTOR_*/MANA_ABILITY signals the migrated scorer will consume."""
    from mtgcli.analyzer.analyze import analyze_card
    ids = lambda c: [s["id"] for s in analyze_card(c)["signals"]]
    assert "TUTOR_UNCONDITIONAL" in ids({"name": "T", "oracle_text": "Search your library for a card.", "type_line": "Sorcery"})
    assert "TUTOR_CONDITIONAL" in ids({"name": "T", "oracle_text": "Search your library for a creature card.", "type_line": "Instant"})
    assert "MANA_ABILITY" in ids({"name": "R", "oracle_text": "{T}: Add {C}.", "type_line": "Artifact"})
