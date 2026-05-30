import json
import pytest
from pathlib import Path
from mtgcli.config import SEED_DATA_DIR
from mtgcli.deckbuilder.skeleton_adjuster import (
    resolve_flexible_value,
    get_flexible_land_range,
    resolve_skeleton_to_int,
    apply_constraints_to_skeleton,
    normalize_deck_to_legal_size,
    get_main_deck_size,
)
from mtgcli.deckbuilder.constraints import DeckConstraints


# --- skeleton schema ---

def test_landfall_lands_is_flexible_range():
    path = SEED_DATA_DIR / "deck_skeletons.json"
    skeletons = json.loads(path.read_text())
    lands = skeletons["landfall_landsmatter"]["lands"]
    assert isinstance(lands, dict), "lands should be a flexible_range object, not a hard integer"
    assert lands["mode"] == "flexible_range"


def test_landfall_flexible_range_values():
    path = SEED_DATA_DIR / "deck_skeletons.json"
    skeletons = json.loads(path.read_text())
    lands = skeletons["landfall_landsmatter"]["lands"]
    assert lands["min"] == 38
    assert lands["target"] == 40
    assert lands["max"] == 42


def test_landfall_lands_is_not_hard_40():
    path = SEED_DATA_DIR / "deck_skeletons.json"
    skeletons = json.loads(path.read_text())
    assert skeletons["landfall_landsmatter"]["lands"] != 40


def test_all_other_skeletons_lands_are_strings():
    """Non-landfall skeletons should keep formula strings (not hard integers)."""
    path = SEED_DATA_DIR / "deck_skeletons.json"
    skeletons = json.loads(path.read_text())
    for name, sk in skeletons.items():
        if name == "landfall_landsmatter":
            continue
        assert isinstance(sk["lands"], str), f"Skeleton '{name}' lands should be a formula string"


# --- resolve_flexible_value ---

def test_resolve_int():
    assert resolve_flexible_value(10) == 10

def test_resolve_flexible_range_returns_target():
    v = {"mode": "flexible_range", "min": 38, "target": 40, "max": 42}
    assert resolve_flexible_value(v) == 40

def test_resolve_flexible_range_with_override():
    v = {"mode": "flexible_range", "min": 38, "target": 40, "max": 42}
    assert resolve_flexible_value(v, constraint_override=38) == 38

def test_resolve_formula_string():
    # String formulas resolve to a sensible default (35) for math purposes
    assert resolve_flexible_value("calculate_by_formula") == 35

def test_resolve_override_beats_int():
    assert resolve_flexible_value(10, constraint_override=7) == 7


# --- get_flexible_land_range ---

def test_get_land_range_flexible():
    sk = {"lands": {"mode": "flexible_range", "min": 38, "target": 40, "max": 42}}
    r = get_flexible_land_range(sk)
    assert r == {"min": 38, "target": 40, "max": 42}

def test_get_land_range_int():
    sk = {"lands": 36}
    assert get_flexible_land_range(sk) is None

def test_get_land_range_string():
    sk = {"lands": "calculate_by_formula"}
    assert get_flexible_land_range(sk) is None


# --- resolve_skeleton_to_int ---

def test_resolve_skeleton_to_int_landfall():
    path = SEED_DATA_DIR / "deck_skeletons.json"
    skeletons = json.loads(path.read_text())
    resolved = resolve_skeleton_to_int(skeletons["landfall_landsmatter"])
    assert isinstance(resolved["lands"], int)
    assert resolved["lands"] == 40  # target


def test_resolve_skeleton_to_int_with_land_override():
    path = SEED_DATA_DIR / "deck_skeletons.json"
    skeletons = json.loads(path.read_text())
    resolved = resolve_skeleton_to_int(skeletons["landfall_landsmatter"], land_override=38)
    assert resolved["lands"] == 38


# --- apply_constraints_to_skeleton ---

def test_apply_constraints_landfall_totals_100():
    path = SEED_DATA_DIR / "deck_skeletons.json"
    skeletons = json.loads(path.read_text())
    constraints = DeckConstraints()
    result = apply_constraints_to_skeleton(skeletons["landfall_landsmatter"], constraints)
    assert sum(result.values()) == 100


def test_apply_constraints_landfall_lands_near_40():
    path = SEED_DATA_DIR / "deck_skeletons.json"
    skeletons = json.loads(path.read_text())
    constraints = DeckConstraints()
    result = apply_constraints_to_skeleton(skeletons["landfall_landsmatter"], constraints)
    assert 38 <= result["lands"] <= 42


def test_apply_constraints_exact_land_count_overrides():
    path = SEED_DATA_DIR / "deck_skeletons.json"
    skeletons = json.loads(path.read_text())
    constraints = DeckConstraints(exact_counts={"lands": 38})
    result = apply_constraints_to_skeleton(skeletons["landfall_landsmatter"], constraints)
    assert result["lands"] == 38
    assert sum(result.values()) == 100


def test_apply_constraints_generic_skeleton_totals_100():
    path = SEED_DATA_DIR / "deck_skeletons.json"
    skeletons = json.loads(path.read_text())
    constraints = DeckConstraints()
    result = apply_constraints_to_skeleton(skeletons["generic_commander"], constraints)
    assert sum(result.values()) == 100


# --- normalize_deck_to_legal_size ---

def test_normalize_trims_oversized():
    slots = {"commander_slots": 1, "lands": 40, "synergy": 10, "ramp": 55}
    result = normalize_deck_to_legal_size(slots, commander_slots=1)
    assert sum(result.values()) == 100

def test_normalize_trims_synergy_first():
    # total=106, need to cut 6; synergy(10) absorbs all 6 cuts → synergy=4, ramp untouched
    slots = {"commander_slots": 1, "lands": 40, "synergy": 10, "ramp": 55}
    result = normalize_deck_to_legal_size(slots, commander_slots=1)
    assert result["ramp"] == 55  # ramp not touched
    assert result["synergy"] < 10  # synergy was reduced

def test_normalize_respects_land_minimum():
    # Even if oversized, don't cut lands below min
    slots = {"commander_slots": 1, "lands": 40, "synergy": 0, "ramp": 65}
    land_range = {"min": 38, "target": 40, "max": 42}
    result = normalize_deck_to_legal_size(slots, land_range=land_range)
    assert result["lands"] >= 38

def test_normalize_fills_undersized():
    slots = {"commander_slots": 1, "lands": 30, "ramp": 10}
    result = normalize_deck_to_legal_size(slots)
    assert sum(result.values()) == 100

def test_normalize_already_legal():
    slots = {"commander_slots": 1, "lands": 40, "ramp": 59}
    result = normalize_deck_to_legal_size(slots)
    assert sum(result.values()) == 100

def test_normalize_partner_target():
    # Partner deck: total still 100 (commander_slots=2 included in slots)
    slots = {"commander_slots": 2, "lands": 40, "ramp": 12, "synergy": 50}
    result = normalize_deck_to_legal_size(slots, commander_slots=2)
    assert sum(result.values()) == 100
