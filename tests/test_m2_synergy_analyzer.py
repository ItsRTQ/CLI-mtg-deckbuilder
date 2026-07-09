"""M2 consumer #3: suggest --synergy / wanted_card_patterns consume the analyzer.

- _analyzer_synergy_phrases translates high/very_high bands into the measured card_tags
  phrases of the archetype's rule tokens (the analyzer's own vocabulary — same map as
  deck-gaps), tribal bands into the creature type.
- The no-analysis fallback of extract_commander_synergy_signals also gets the analyzer
  read (pure logic, no DB needed).
"""
from mtgcli.deckbuilder.suggestion_scorer import (
    _analyzer_synergy_phrases,
    extract_commander_synergy_signals,
)


def test_high_band_yields_tag_phrases():
    phrases = _analyzer_synergy_phrases([{"archetype": "Go Wide", "band": "high"}])
    assert "create a token" in phrases or "creature token" in phrases
    assert phrases  # non-empty


def test_low_band_yields_nothing():
    assert _analyzer_synergy_phrases([{"archetype": "Go Wide", "band": "low"}]) == set()


def test_tribal_band_yields_type_word():
    assert "dragon" in _analyzer_synergy_phrases(
        [{"archetype": "Dragon Tribal", "band": "high"}])


def test_garbage_is_guarded():
    assert _analyzer_synergy_phrases(None) == set()
    assert _analyzer_synergy_phrases([{"weird": True}]) == set()


def test_fallback_extraction_includes_analyzer_phrases():
    krenko = {
        "name": "Krenko, Mob Boss",
        "oracle_text": "{T}: Create X 1/1 red Goblin creature tokens, "
                       "where X is the number of Goblins you control.",
        "type_line": "Legendary Creature — Goblin Warrior",
    }
    signals = extract_commander_synergy_signals(krenko, analysis_path=None)
    # Legacy heuristic signals still present...
    assert "goblin" in signals
    # ...plus the analyzer's Go Wide plan phrases (Krenko reads Go Wide high).
    assert "creature token" in signals or "create a token" in signals
