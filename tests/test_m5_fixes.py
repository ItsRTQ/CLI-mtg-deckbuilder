"""Regressions for the two M5 build frictions (Galadriel test build).

Friction 1 (detection class): ability-word-prefixed triggers ("Alliance — Whenever ...",
"Landfall — Whenever ...") were invisible to extract_trigger_events because the clause no
longer STARTS with a trigger word — 968 cards measured.

Friction 2 (data class): Scryfall token printings shared real card names and shadowed
them in exact-name lookups (the eternalize TOKEN of Timeless Witness reported
commander_legal=False for a legal card). Nonplayable layouts are now excluded at ingest.
"""
import pytest

from mtgcli.config import SQLITE_PATH
from mtgcli.data.normalize_cards import NONPLAYABLE_LAYOUTS
from mtgcli.deckbuilder.oracle_hooks import extract_trigger_events

GALADRIEL = ("Alliance — Whenever another creature you control enters, choose one that "
             "hasn't been chosen this turn —\n• Add {G}{G}{G}.\n"
             "• Put a +1/+1 counter on each creature you control.\n"
             "• Scry 2, then draw a card.")


def test_ability_word_prefixed_trigger_detected():
    assert "permanent_enters" in extract_trigger_events(GALADRIEL)


def test_landfall_prefixed_trigger_detected():
    # Classification reads the trigger CONDITION only (before the first comma) — the
    # event here is a land entering; "you gain 4 life" is the effect, not the event.
    text = "Landfall — Whenever a land you control enters, you gain 4 life."
    assert "permanent_enters" in extract_trigger_events(text)


def test_unprefixed_triggers_unchanged():
    assert "permanent_dies" in extract_trigger_events("Whenever a creature dies, draw a card.")
    assert extract_trigger_events("Flying, vigilance") == []


def test_nonplayable_layouts_frozen():
    assert {"token", "double_faced_token", "emblem", "art_series"} <= NONPLAYABLE_LAYOUTS
    # Real playable layouts must never be excluded.
    for keep in ("normal", "transform", "modal_dfc", "adventure", "split", "saga", "meld"):
        assert keep not in NONPLAYABLE_LAYOUTS


@pytest.mark.skipif(not SQLITE_PATH.exists(), reason="card DB not built")
def test_db_has_no_token_shadows():
    import sqlite3
    conn = sqlite3.connect(str(SQLITE_PATH))
    n = conn.execute(
        "SELECT COUNT(*) FROM cards WHERE layout IN "
        "('token','double_faced_token','emblem','art_series','vanguard','scheme','planar')"
    ).fetchone()[0]
    assert n == 0
    rows = conn.execute(
        "SELECT commander_legal, type_line FROM cards WHERE name='Timeless Witness'"
    ).fetchall()
    assert len(rows) == 1 and rows[0][0] == 1 and not rows[0][1].startswith("Token")
