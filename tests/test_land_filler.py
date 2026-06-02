import json
import pytest
from pathlib import Path
from mtgcli.deckbuilder.land_filler import (
    calculate_land_distribution,
    fill_deck_with_lands,
    remove_command_zone_cards_from_main_deck,
)
from mtgcli.utils.decklist_parser import parse_decklist_text


# --- calculate_land_distribution ---

def test_single_color_all_same_land():
    dist = calculate_land_distribution(["W"], 5)
    assert dist == {"Plains": 5}

def test_two_colors_even_split():
    dist = calculate_land_distribution(["W", "U"], 6)
    assert dist == {"Plains": 3, "Island": 3}

def test_three_colors_esper():
    dist = calculate_land_distribution(["W", "U", "B"], 9)
    assert dist == {"Plains": 3, "Island": 3, "Swamp": 3}

def test_three_colors_esper_uneven():
    # 8 slots for WUB: 2+3+3 or 3+3+2 — WUBRG order: W first gets extra
    dist = calculate_land_distribution(["W", "U", "B"], 8)
    assert sum(dist.values()) == 8
    assert "Plains" in dist and "Island" in dist and "Swamp" in dist

def test_grixis_identity():
    dist = calculate_land_distribution(["U", "B", "R"], 7)
    assert sum(dist.values()) == 7
    assert "Island" in dist
    assert "Swamp" in dist
    assert "Mountain" in dist
    assert "Plains" not in dist
    assert "Forest" not in dist

def test_colorless_identity_adds_wastes():
    dist = calculate_land_distribution([], 5)
    assert dist == {"Wastes": 5}

def test_zero_slots_returns_empty():
    dist = calculate_land_distribution(["W", "U", "B"], 0)
    assert dist == {}

def test_wubrg_order_remainder_goes_to_w_first():
    # 7 slots for WUBRG: base=1, remainder=2 → W=2, U=2, B=1, R=1, G=1
    dist = calculate_land_distribution(["W", "U", "B", "R", "G"], 7)
    assert sum(dist.values()) == 7
    assert dist["Plains"] == 2
    assert dist["Island"] == 2

def test_identity_not_in_wubrg_ignored():
    # 'C' (generic colorless) should be ignored, falls back to Wastes
    dist = calculate_land_distribution(["C"], 3)
    assert dist == {"Wastes": 3}


# --- fill_deck_with_lands ---

def _make_deck(n, prefix="Card"):
    return [{"name": f"{prefix} {i}", "quantity": 1} for i in range(n)]

def test_single_commander_target_defaults_99():
    # 91 cards → needs 8 basics
    deck = _make_deck(91)
    result = fill_deck_with_lands(deck, ["W"], 99)
    assert result["filled"] is True
    assert result["remaining_slots"] == 8
    assert result["lands_added"]["Plains"] == 8

def test_partner_target_98():
    deck = _make_deck(91)
    result = fill_deck_with_lands(deck, ["W"], 98)
    assert result["remaining_slots"] == 7
    assert result["lands_added"]["Plains"] == 7

def test_esper_identity_fills_correct_lands():
    deck = _make_deck(91)
    result = fill_deck_with_lands(deck, ["W", "U", "B"], 99)
    assert result["filled"] is True
    lands = result["lands_added"]
    assert sum(lands.values()) == 8
    for land in lands:
        assert land in {"Plains", "Island", "Swamp"}

def test_grixis_identity_fills_correct_lands():
    deck = _make_deck(92)
    result = fill_deck_with_lands(deck, ["U", "B", "R"], 99)
    lands = result["lands_added"]
    assert sum(lands.values()) == 7
    for land in lands:
        assert land in {"Island", "Swamp", "Mountain"}

def test_colorless_identity_adds_wastes():
    deck = _make_deck(97)
    result = fill_deck_with_lands(deck, [], 99)
    assert result["lands_added"] == {"Wastes": 2}

def test_exact_size_no_changes():
    deck = _make_deck(99)
    result = fill_deck_with_lands(deck, ["W"], 99)
    assert result["filled"] is True
    assert result["lands_added"] == {}
    assert result["remaining_slots"] == 0
    assert "note" in result

def test_over_target_returns_error():
    deck = _make_deck(101)
    result = fill_deck_with_lands(deck, ["W"], 99)
    assert result["filled"] is False
    assert "error" in result
    assert "101" in result["error"]

def test_over_target_does_not_remove_cards():
    deck = _make_deck(101)
    result = fill_deck_with_lands(deck, ["W"], 99)
    assert "updated_deck" not in result

def test_updated_deck_has_correct_total():
    deck = _make_deck(91)
    result = fill_deck_with_lands(deck, ["W", "U"], 99)
    updated = result["updated_deck"]
    total = sum(e["quantity"] for e in updated)
    assert total == 99

def test_existing_land_quantity_updated():
    deck = [{"name": "Plains", "quantity": 5}, {"name": "Sol Ring", "quantity": 1}]
    result = fill_deck_with_lands(deck, ["W"], 10)
    updated = result["updated_deck"]
    plains = next(e for e in updated if e["name"] == "Plains")
    assert plains["quantity"] == 5 + result["lands_added"].get("Plains", 0)

def test_preserves_nonland_cards():
    deck = [
        {"name": "Sol Ring", "quantity": 1},
        {"name": "Arcane Signet", "quantity": 1},
    ]
    result = fill_deck_with_lands(deck, ["W"], 5)
    updated = result["updated_deck"]
    names = [e["name"] for e in updated]
    assert "Sol Ring" in names
    assert "Arcane Signet" in names

def test_flat_and_structured_deck_both_work():
    # fill_deck_with_lands takes already-normalized deck_entries (flat list)
    flat = [{"name": "Sol Ring", "quantity": 1}]
    result = fill_deck_with_lands(flat, ["U"], 3)
    assert result["remaining_slots"] == 2
    assert result["lands_added"]["Island"] == 2


# --- decklist_parser ---

def test_parse_simple_decklist():
    text = "1 Sol Ring\n1 Arcane Signet\n"
    entries = parse_decklist_text(text)
    assert len(entries) == 2
    assert entries[0] == {"name": "Sol Ring", "quantity": 1}

def test_parse_1x_format():
    entries = parse_decklist_text("1x Sol Ring\n")
    assert entries[0]["quantity"] == 1
    assert entries[0]["name"] == "Sol Ring"

def test_parse_missing_quantity_defaults_to_1():
    entries = parse_decklist_text("Sol Ring\n")
    assert entries[0]["quantity"] == 1
    assert entries[0]["name"] == "Sol Ring"

def test_parse_ignores_comments():
    text = "# Ramp\n1 Sol Ring\n## Lands\n1 Forest\n"
    entries = parse_decklist_text(text)
    assert len(entries) == 2
    assert entries[0]["name"] == "Sol Ring"
    assert entries[1]["name"] == "Forest"

def test_parse_ignores_empty_lines():
    text = "\n1 Sol Ring\n\n1 Forest\n"
    entries = parse_decklist_text(text)
    assert len(entries) == 2

def test_parse_multiword_card_name():
    entries = parse_decklist_text("1 Command Tower\n")
    assert entries[0]["name"] == "Command Tower"

def test_parse_quantity_with_uppercase_x():
    entries = parse_decklist_text("2X Forest\n")
    assert entries[0]["quantity"] == 2
    assert entries[0]["name"] == "Forest"

def test_parse_returns_empty_list_for_empty_input():
    assert parse_decklist_text("") == []
    assert parse_decklist_text("# only comments\n") == []


# --- remove_command_zone_cards_from_main_deck ---

def test_remove_commander_from_flat_deck():
    deck = [
        {"name": "Edgar Markov", "quantity": 1},
        {"name": "Sol Ring", "quantity": 1},
    ]
    cleaned, removed = remove_command_zone_cards_from_main_deck(deck, ["Edgar Markov"])
    assert len(cleaned) == 1
    assert cleaned[0]["name"] == "Sol Ring"
    assert removed == ["Edgar Markov"]


def test_remove_commander_case_insensitive():
    deck = [
        {"name": "edgar markov", "quantity": 1},
        {"name": "Arcane Signet", "quantity": 1},
    ]
    cleaned, removed = remove_command_zone_cards_from_main_deck(deck, ["Edgar Markov"])
    assert len(cleaned) == 1
    assert removed == ["edgar markov"]


def test_remove_both_partners():
    deck = [
        {"name": "Tymna the Weaver", "quantity": 1},
        {"name": "Thrasios, Triton Hero", "quantity": 1},
        {"name": "Sol Ring", "quantity": 1},
    ]
    cleaned, removed = remove_command_zone_cards_from_main_deck(
        deck, ["Tymna the Weaver", "Thrasios, Triton Hero"]
    )
    assert len(cleaned) == 1
    assert "Sol Ring" == cleaned[0]["name"]
    assert len(removed) == 2


def test_no_commander_in_deck_no_removal():
    deck = [{"name": "Sol Ring", "quantity": 1}]
    cleaned, removed = remove_command_zone_cards_from_main_deck(deck, ["Edgar Markov"])
    assert cleaned == deck
    assert removed == []


def test_flat_deck_with_commander_fills_to_99():
    """Flat deck containing commander should fill main deck to 99 after removal."""
    deck = [{"name": "Edgar Markov", "quantity": 1}] + _make_deck(90, "Card")
    cleaned, removed = remove_command_zone_cards_from_main_deck(deck, ["Edgar Markov"])
    assert len(cleaned) == 90
    result = fill_deck_with_lands(cleaned, ["W", "B", "R"], 99)
    assert result["filled"] is True
    updated_total = sum(e["quantity"] for e in result["updated_deck"])
    assert updated_total == 99


def test_partner_deck_fills_to_98():
    """After removing two partners, fill to 98."""
    partners = [
        {"name": "Tymna the Weaver", "quantity": 1},
        {"name": "Thrasios, Triton Hero", "quantity": 1},
    ]
    deck = partners + _make_deck(90, "Card")
    cleaned, removed = remove_command_zone_cards_from_main_deck(
        deck, ["Tymna the Weaver", "Thrasios, Triton Hero"]
    )
    assert len(cleaned) == 90
    result = fill_deck_with_lands(cleaned, ["W", "U", "B", "G"], 98)
    assert result["filled"] is True
    total = sum(e["quantity"] for e in result["updated_deck"])
    assert total == 98
