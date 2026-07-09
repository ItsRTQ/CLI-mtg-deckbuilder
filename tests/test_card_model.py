"""Regression: the CARD build-context object (Consistency-engine Fase 2).

Contract: names arrive PRE-VERIFIED; a miss fails loud Krenkooo-style (error with
fuzzy suggestions + fix instructions). Judgment (purpose list, agent_note) is the
agent's; facts hydrate from the DB and are EPHEMERAL (never persisted stale —
to_dict serializes judgment only).
"""
import json
from pathlib import Path

import pytest

from mtgcli.config import SQLITE_PATH
from mtgcli.models import Card, CardNotFoundError, PURPOSES

needs_db = pytest.mark.skipif(
    not Path(str(SQLITE_PATH)).exists(), reason="card DB not built"
)


def _row(**over):
    base = {
        "name": "Fake Card", "mana_cost": "{1}{R}", "mana_value": 2.0,
        "type_line": "Legendary Creature — Lobster", "oracle_text": "Do things.",
        "power": "2", "toughness": "3", "loyalty": None,
        "colors": '["R"]', "color_identity": '["R"]',
        "keywords": '["Flying"]', "produced_mana": None,
        "all_parts": None, "image_url": "https://img/x.jpg",
        "edhrec_rank": 123, "usd_price": 4.5, "game_changer": 0,
    }
    base.update(over)
    return base


# ---------- judgment ----------

def test_purpose_accepts_one_or_many_and_normalizes():
    assert Card("X", "ramp", db_row=_row()).purpose == ["RAMP"]
    assert Card("X", ["Ramp", "SYNERGY"], db_row=_row()).purpose == ["RAMP", "SYNERGY"]


def test_purpose_controlled_vocabulary():
    with pytest.raises(ValueError) as e:
        Card("X", ["TURBO"], db_row=_row())
    assert "TURBO" in str(e.value) and PURPOSES[0] in str(e.value)


def test_gc_purpose_auto_added_from_flag():
    c = Card("X", ["DRAW"], db_row=_row(game_changer=1))
    assert "GC" in c.purpose and c.game_changer


# ---------- fail-loud contract ----------

class _EmptyRepo:
    def get_card_by_exact_name(self, name):
        return None

    def suggest_similar_names(self, name):
        return [{"name": "Krenko, Mob Boss"}]


def test_not_found_fails_loud_with_suggestions_and_fix():
    with pytest.raises(CardNotFoundError) as e:
        Card("Krenkooo", ["RAMP"], repo=_EmptyRepo())
    msg = str(e.value)
    assert "Krenko, Mob Boss" in msg          # did-you-mean
    assert "cards-batch --verify" in msg      # how to fix
    assert e.value.suggestions == ["Krenko, Mob Boss"]


# ---------- fact getters ----------

def test_getters_hydrate_and_parse_json_fields():
    c = Card("X", ["FLEX"], db_row=_row(produced_mana='["R", "W"]', loyalty="4"))
    assert c.keywords == ["Flying"]
    assert c.produced_mana == ["R", "W"]
    assert c.loyalty == "4"
    assert c.color_identity == ["R"]
    assert c.mana_value == 2.0
    assert c.usd_price == 4.5
    assert c.edhrec_rank == 123
    assert c.image_src == "https://img/x.jpg"


def test_card_types_from_type_line_including_kindred():
    c = Card("X", ["FLEX"], db_row=_row(type_line="Kindred Enchantment — Sliver"))
    assert c.card_types == ["enchantment", "kindred"]


def test_all_parts_grouped_and_self_filtered():
    parts = json.dumps([
        {"component": "token", "name": "Food", "type_line": "Token", "id": "1"},
        {"component": "combo_piece", "name": "Fake Card", "type_line": "Artifact", "id": "2"},
        {"component": "meld_part", "name": "Other Half", "type_line": "Creature", "id": "3"},
    ])
    c = Card("Fake Card", ["FLEX"], db_row=_row(all_parts=parts))
    assert c.all_parts == {"token": ["Food"], "meld_part": ["Other Half"]}  # self filtered


# ---------- print (build-facing summary) ----------

def test_str_shows_build_essentials_and_note_wins_over_purpose():
    plain = str(Card("X", ["RAMP"], db_row=_row(produced_mana='["C"]')))
    assert "P/T 2/3" in plain and "produces {C}" in plain and "$4.50" in plain
    assert "purpose: RAMP" in plain          # no note -> purpose printed
    noted = str(Card("X", ["RAMP"], agent_note="es Food bajo Ragost", db_row=_row()))
    assert ">> es Food bajo Ragost" in noted and "purpose:" not in noted


def test_str_quantity_for_basics():
    s = str(Card("Mountain", ["FLEX"], quantity=12,
                 db_row=_row(name="Mountain", type_line="Basic Land — Mountain",
                             power=None, toughness=None)))
    assert "Mountain" in s and "x12" in s


# ---------- serialization (judgment only — facts are ephemeral) ----------

def test_to_dict_serializes_judgment_only_and_roundtrips():
    c = Card("X", ["RAMP", "SYNERGY"], agent_note="why", quantity=2, db_row=_row())
    d = c.to_dict()
    assert d == {"name": "Fake Card", "quantity": 2,
                 "purpose": ["RAMP", "SYNERGY"], "agent_note": "why"}
    assert "oracle_text" not in d and "usd_price" not in d  # never persist facts


# ---------- live DB ----------

@needs_db
def test_live_hydration_sol_ring():
    c = Card("Sol Ring", ["RAMP"])
    assert c.produced_mana == ["C"]
    assert "Add {C}{C}" in c.oracle_text
    assert c.card_types == ["artifact"]


@needs_db
def test_live_dfc_front_face_resolves():
    c = Card("Runo Stromkirk", ["WINCON"])
    assert c.image_src and c.name.startswith("Runo Stromkirk")
