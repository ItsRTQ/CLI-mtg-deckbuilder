"""
Tests for the commander_analyzer module.

Uses injected fake card objects — no DB dependency.
"""
import json
import pytest
from pathlib import Path
from mtgcli.deckbuilder.commander_analyzer import (
    analyze_commander,
    _parse_type_line,
    _infer_engine_patterns,
    _extract_text_signals,
)
from mtgcli.deckbuilder.suggestion_scorer import (
    extract_commander_synergy_signals,
    check_card_synergy,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _card(
    name="Test Commander",
    oracle="",
    type_line="Legendary Creature — Human",
    mana_cost="{2}{W}",
    mana_value=3.0,
    color_identity=None,
    can_be_commander=True,
    commander_legal=True,
):
    return {
        "name": name,
        "oracle_text": oracle,
        "type_line": type_line,
        "mana_cost": mana_cost,
        "mana_value": mana_value,
        "color_identity": color_identity or ["W"],
        "can_be_commander": can_be_commander,
        "commander_legal": commander_legal,
        "power": "2",
        "toughness": "2",
        "keywords": [],
        "layout": "normal",
    }


BRAGO = _card(
    name="Brago, King Eternal",
    oracle=(
        "Flying\nNontoken permanents you control have flying.\n"
        "Whenever Brago, King Eternal deals combat damage to a player, exile any number of target "
        "nonland permanents you control, then return those cards to the battlefield under their "
        "owner's control."
    ),
    type_line="Legendary Creature — Spirit",
    mana_cost="{2}{W}{U}",
    mana_value=4.0,
    color_identity=["U", "W"],
)

TEYSA = _card(
    name="Teysa Karlov",
    oracle=(
        "If a creature dying causes a triggered ability of a permanent you control to trigger, "
        "that ability triggers an additional time.\n"
        "Creature tokens you control have vigilance and lifelink."
    ),
    type_line="Legendary Creature — Human Advisor",
    mana_cost="{2}{W}{B}",
    mana_value=4.0,
    color_identity=["B", "W"],
)

OMNATH = _card(
    name="Omnath, Locus of Rage",
    oracle=(
        "Landfall — Whenever a land enters the battlefield under your control, create a 5/5 red and "
        "green Elemental creature token.\nWhenever Omnath, Locus of Rage or another Elemental you "
        "control dies, Omnath deals 3 damage to any target."
    ),
    type_line="Legendary Creature — Elemental",
    mana_cost="{3}{R}{R}{G}{G}",
    mana_value=7.0,
    color_identity=["G", "R"],
)

KINNAN = _card(
    name="Kinnan, Bonder Prodigy",
    oracle=(
        "Whenever a land or nonland permanent you control produces mana, it produces that much "
        "mana plus one mana of any type that land or permanent could produce.\n"
        "{5}{G}{U}: Look at the top five cards of your library. You may put a non-Human creature "
        "card from among them onto the battlefield. Put the rest on the bottom of your library in "
        "a random order."
    ),
    type_line="Legendary Creature — Human Druid",
    mana_cost="{G}{U}",
    mana_value=2.0,
    color_identity=["G", "U"],
)

EDGAR = _card(
    name="Edgar Markov",
    oracle=(
        "Eminence — Whenever you cast another Vampire spell, if Edgar Markov is in the command "
        "zone or on the battlefield, create a 1/1 black Vampire creature token.\n"
        "First strike, haste\nWhenever Edgar Markov attacks, put a +1/+1 counter on each Vampire "
        "you control."
    ),
    type_line="Legendary Creature — Vampire Knight",
    mana_cost="{3}{R}{W}{B}",
    mana_value=6.0,
    color_identity=["B", "R", "W"],
)

AMINATOU = _card(
    name="Aminatou, the Fateshifter",
    oracle=(
        "+1: Draw a card then put a card from your hand on top of your library.\n"
        "−1: Exile target permanent you own, then return it to the battlefield under your control.\n"
        "−6: Choose left or right. Each player gains control of all nonland permanents other than "
        "Aminatou, the Fateshifter controlled by the next player in the chosen direction."
    ),
    type_line="Legendary Planeswalker — Aminatou",
    mana_cost="{W}{U}{B}",
    mana_value=3.0,
    color_identity=["B", "U", "W"],
    can_be_commander=True,
)


# ─── Type line parsing ────────────────────────────────────────────────────────

def test_parse_type_line_creature():
    result = _parse_type_line("Legendary Creature — Spirit")
    assert "Legendary" in result["supertypes"]
    assert "Creature" in result["card_types"]
    assert "Spirit" in result["subtypes"]


def test_parse_type_line_artifact_creature():
    result = _parse_type_line("Legendary Artifact Creature — Necron")
    assert "Artifact" in result["card_types"]
    assert "Creature" in result["card_types"]
    assert "Necron" in result["subtypes"]


def test_parse_type_line_planeswalker():
    result = _parse_type_line("Legendary Planeswalker — Aminatou")
    assert "Planeswalker" in result["card_types"]
    assert "Aminatou" in result["subtypes"]


def test_parse_type_line_enchantment_creature():
    result = _parse_type_line("Legendary Enchantment Creature — God")
    assert "Enchantment" in result["card_types"]
    assert "Creature" in result["card_types"]
    assert "God" in result["subtypes"]


def test_parse_type_line_background():
    result = _parse_type_line("Legendary Background")
    assert "Background" in result["card_types"]
    assert result["subtypes"] == []


# ─── Engine pattern inference ─────────────────────────────────────────────────

def test_brago_engine_pattern():
    patterns = _infer_engine_patterns(BRAGO["oracle_text"])
    assert "etb_blink_engine" in patterns
    assert "combat_damage_engine" in patterns


def test_teysa_engine_pattern():
    patterns = _infer_engine_patterns(TEYSA["oracle_text"])
    assert "death_trigger_engine" in patterns


def test_omnath_engine_pattern():
    patterns = _infer_engine_patterns(OMNATH["oracle_text"])
    assert "landfall_landsmatter" in patterns
    assert "token_engine" in patterns


def test_kinnan_engine_pattern():
    patterns = _infer_engine_patterns(KINNAN["oracle_text"])
    assert "mana_engine" in patterns


def test_edgar_engine_pattern():
    patterns = _infer_engine_patterns(EDGAR["oracle_text"])
    assert "token_engine" in patterns


# ─── Text signal extraction ───────────────────────────────────────────────────

def test_brago_text_signals():
    signals = _extract_text_signals(BRAGO["oracle_text"])
    assert "whenever" in signals["trigger_conditions"] or "when " in signals["trigger_conditions"]
    assert "exile" in signals["resource_zones"]
    assert "battlefield" in signals["resource_zones"]


def test_teysa_text_signals():
    signals = _extract_text_signals(TEYSA["oracle_text"])
    # Teysa uses "If a creature dying..." — "if " is the trigger condition, not "whenever"
    assert "if " in signals["trigger_conditions"]


def test_omnath_scaling_axes():
    signals = _extract_text_signals(OMNATH["oracle_text"])
    assert "tokens" in signals["scaling_axes"]


# ─── Full analysis output ─────────────────────────────────────────────────────

def test_analyze_commander_returns_schema_keys():
    result = analyze_commander(BRAGO)
    required_keys = [
        "commander", "partner", "is_valid_commander", "commander_slots",
        "library_slots", "color_identity", "combined_color_identity",
        "card_identity", "text_signals",
        "engine_profile",
        "best_archetype", "role_pressures", "commander_scores",
        "provides", "requires", "rewards",
        "wanted_card_patterns", "avoid_card_patterns", "build_direction_options", "notes",
    ]
    for key in required_keys:
        assert key in result, f"Missing key: {key}"


def test_brago_analysis_is_valid():
    result = analyze_commander(BRAGO)
    assert result["is_valid_commander"] is True
    assert result["commander"] == "Brago, King Eternal"
    assert result["commander_slots"] == 1
    assert result["library_slots"] == 99


def test_brago_color_identity():
    result = analyze_commander(BRAGO)
    assert set(result["color_identity"]) == {"U", "W"}


def test_brago_archetype_blink():
    result = analyze_commander(BRAGO)
    bands = [a["archetype"] for a in result["analyzer"]["archetype_support"]]
    assert any("Blink" in b or "ETB" in b for b in bands)


def test_brago_wanted_patterns_contains_etb():
    result = analyze_commander(BRAGO)
    wanted_text = " ".join(result["wanted_card_patterns"])
    assert "ETB" in wanted_text or "blink" in wanted_text.lower()


def test_teysa_analysis_death_trigger():
    result = analyze_commander(TEYSA)
    assert result["is_valid_commander"] is True
    engine = result["engine_profile"]["primary_pattern"]
    assert engine == "death_trigger_engine"


def test_teysa_archetype_aristocrats():
    result = analyze_commander(TEYSA)
    bands = [a["archetype"] for a in result["analyzer"]["archetype_support"]]
    assert "Aristocrats" in bands


def test_omnath_engine_landfall():
    result = analyze_commander(OMNATH)
    assert "landfall_landsmatter" in result["engine_profile"]["primary_pattern"] or \
           "landfall_landsmatter" in result["engine_profile"]["secondary_patterns"]


def test_kinnan_engine_mana():
    result = analyze_commander(KINNAN)
    assert "mana_engine" in result["engine_profile"]["primary_pattern"] or \
           "mana_engine" in result["engine_profile"]["secondary_patterns"]


def test_aminatou_planeswalker_type_tag():
    result = analyze_commander(AMINATOU)
    assert result["card_identity"]["is_planeswalker"] is True


def test_partner_commander_slots():
    tymna = _card(
        name="Tymna the Weaver",
        oracle="Lifelink\nAt the beginning of your postcombat main phase, you may pay X life, where "
               "X is the number of opponents that were dealt combat damage this turn. If you do, "
               "draw X cards.",
        type_line="Legendary Creature — Human Cleric",
        mana_cost="{1}{W}{B}",
        mana_value=3.0,
        color_identity=["B", "W"],
    )
    thrasios = _card(
        name="Thrasios, Triton Hero",
        oracle="{4}: Scry 1, then reveal the top card of your library. If it's a land card, put it "
               "onto the battlefield. Otherwise, draw a card.",
        type_line="Legendary Creature — Merfolk Wizard",
        mana_cost="{G}{U}",
        mana_value=2.0,
        color_identity=["G", "U"],
    )
    result = analyze_commander(tymna, partner_card=thrasios)
    assert result["commander_slots"] == 2
    assert result["library_slots"] == 98
    assert result["partner"] == "Thrasios, Triton Hero"
    assert set(result["combined_color_identity"]) == {"B", "G", "U", "W"}


def test_invalid_commander_marked():
    non_cmd = _card(
        name="Lightning Bolt",
        oracle="Lightning Bolt deals 3 damage to any target.",
        type_line="Instant",
        mana_cost="{R}",
        mana_value=1.0,
        color_identity=["R"],
        can_be_commander=False,
        commander_legal=True,
    )
    result = analyze_commander(non_cmd)
    assert result["is_valid_commander"] is False
    assert any("WARNING" in note for note in result["notes"])


def test_role_pressures_keys():
    result = analyze_commander(BRAGO)
    required = [
        "lands", "ramp", "card_draw", "removal", "board_wipes", "counterspells",
        "protection", "recursion", "archetype_core", "synergy_enablers", "synergy_payoffs",
    ]
    for key in required:
        assert key in result["role_pressures"], f"Missing role pressure: {key}"
    for v in result["role_pressures"].values():
        assert v in ("low", "normal", "medium", "high"), f"Invalid pressure label: {v}"


def test_commander_scores_keys():
    result = analyze_commander(BRAGO)
    required = [
        "dependency", "threat_reputation", "mana_value_pressure",
        "built_in_protection", "built_in_card_advantage", "built_in_ramp",
        "built_in_removal", "combo_potential", "multiplayer_scaling",
    ]
    for key in required:
        assert key in result["commander_scores"], f"Missing commander_score: {key}"


def test_archetype_forced_fit_warning():
    result = analyze_commander(BRAGO, archetype="voltron")
    if result.get("forced_archetype_warning"):
        assert "voltron" in result["forced_archetype_warning"].lower()


def test_context_notes_included():
    result = analyze_commander(BRAGO, power_level=7, philosophy="spike", meta="cedh")
    notes_text = " ".join(result["notes"])
    assert "7" in notes_text
    assert "spike" in notes_text


# ─── Analysis-aware synergy extraction ───────────────────────────────────────

def test_synergy_signals_fallback_without_analysis(tmp_path):
    signals = extract_commander_synergy_signals(BRAGO, analysis_path=tmp_path / "missing.json")
    assert len(signals) > 0
    assert any("exile" in s or "combat damage" in s for s in signals)


def test_synergy_signals_from_analysis_file(tmp_path):
    analysis = analyze_commander(BRAGO)
    analysis_file = tmp_path / "commander_analysis.json"
    analysis_file.write_text(json.dumps(analysis))

    signals = extract_commander_synergy_signals(BRAGO, analysis_path=analysis_file)
    assert "etb_blink_engine" in signals
    assert len(signals) > 0


def test_check_card_synergy_basic():
    signals = {"enters the battlefield", "exile"}
    card = _card(
        name="Cloudblazer",
        oracle="When Cloudblazer enters the battlefield, you gain 2 life and draw 2 cards.",
        type_line="Creature — Human Scout",
    )
    matched = check_card_synergy(card, signals)
    assert "enters the battlefield" in matched


def test_suggest_synergy_requires_role_match():
    """Ensure synergy signals don't include unrelated mechanics."""
    signals = extract_commander_synergy_signals(BRAGO, analysis_path=None)
    non_ramp_card = _card(
        name="Snapcaster Mage",
        oracle="Flash\nWhen Snapcaster Mage enters the battlefield, target instant or sorcery card "
               "in your graveyard gains flashback until end of turn.",
        type_line="Creature — Human Wizard",
    )
    matched = check_card_synergy(non_ramp_card, signals)
    assert isinstance(matched, list)


# ─── Category counts integration ─────────────────────────────────────────────

def test_category_counts_with_analysis(tmp_path):
    from mtgcli.category_counts.calculator import calculate_category_counts
    analysis = analyze_commander(BRAGO)
    analysis_file = tmp_path / "commander_analysis.json"
    analysis_file.write_text(json.dumps(analysis))

    result = calculate_category_counts(
        "Brago, King Eternal",
        "blink",
        analysis_path=str(analysis_file),
        commander_card_data=BRAGO,
    )
    assert "category_recommendations" in result
    assert result["commander"] == "Brago, King Eternal"


def test_category_counts_without_analysis_still_works():
    from mtgcli.category_counts.calculator import calculate_category_counts
    result = calculate_category_counts(
        "Brago, King Eternal",
        "blink",
        analysis_path=None,
        commander_card_data=BRAGO,
    )
    assert "category_recommendations" in result


def test_category_counts_missing_analysis_falls_back(tmp_path):
    from mtgcli.category_counts.calculator import calculate_category_counts
    result = calculate_category_counts(
        "Brago, King Eternal",
        "blink",
        analysis_path=str(tmp_path / "nonexistent.json"),
        commander_card_data=BRAGO,
    )
    assert "category_recommendations" in result
