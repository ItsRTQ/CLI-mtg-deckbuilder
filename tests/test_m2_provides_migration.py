"""M2 consumer #1: _score_provides consumes analyzer signals, oracle heuristics as fallback.

Contract under test (Fase 2 migration, gate opened by batch #15):
- signals=None  -> exact legacy behavior (callers without an analyzer are untouched).
- signal present -> it REPLACES its oracle twin (same score, no double counting).
- signal absent but oracle phrasing present -> the oracle fallback still fires
  (coverage the narrow signal regexes don't have is preserved).
- the migration IMPROVES the Esika class: "{T}: Add one mana of any color" carries
  MANA_ABILITY but matches neither "add {" nor "add mana", so legacy scored 0 ramp.
"""
from mtgcli.category_counts.scoring import _score_provides, score_commander


def test_signals_none_is_exact_legacy():
    oracle = "search your library for a card. {t}: add {c}."
    assert _score_provides(oracle) == _score_provides(oracle, signals=None)


def test_tutor_unconditional_signal_matches_legacy_score():
    oracle = "search your library for a card, then shuffle."
    legacy = _score_provides(oracle)
    migrated = _score_provides(oracle, signals=["TUTOR_UNCONDITIONAL"])
    assert legacy["tutors"] == migrated["tutors"] == 3.0


def test_tutor_conditional_signal_matches_legacy_score():
    oracle = "search your library for a dragon card and put it into your hand."
    legacy = _score_provides(oracle)
    migrated = _score_provides(oracle, signals=["TUTOR_CONDITIONAL"])
    assert legacy["tutors"] == migrated["tutors"] == 1.5


def test_oracle_fallback_survives_when_signal_absent():
    # "for two ..." doesn't match the conditional-tutor regex (requires a/an/up to),
    # so no signal fires — the legacy substring branch must still score it.
    oracle = "search your library for two basic land cards."
    migrated = _score_provides(oracle, signals=["SCALES_WITH"])  # unrelated signal only
    assert migrated["tutors"] == 1.5


def test_mana_ability_signal_improves_esika_class():
    # Legacy substring twins ("add {" / "add mana") miss this phrasing entirely.
    oracle = "{t}: add one mana of any color."
    assert "normal_ramp" not in _score_provides(oracle)          # legacy: blind
    migrated = _score_provides(oracle, signals=["MANA_ABILITY"])
    assert migrated["normal_ramp"] == 2.5                        # analyzer: sees it


def test_no_double_counting_when_signal_and_oracle_both_present():
    oracle = "{t}: add {g}."
    legacy = _score_provides(oracle)
    migrated = _score_provides(oracle, signals=["MANA_ABILITY"])
    assert legacy["normal_ramp"] == migrated["normal_ramp"] == 2.5


def test_score_commander_passes_signals_through():
    card = {"name": "T", "oracle_text": "{T}: Add one mana of any color.",
            "type_line": "Legendary Creature", "mana_value": 3}
    without = score_commander(card, "tokens")
    with_sig = score_commander(card, "tokens", signals=["MANA_ABILITY"])
    assert without["built_in_ramp"] == 0.0
    assert with_sig["built_in_ramp"] == 2.5
