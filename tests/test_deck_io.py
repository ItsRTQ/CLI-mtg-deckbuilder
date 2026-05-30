import pytest
from mtgcli.utils.deck_io import normalize_deck_input


# --- flat list input ---

def test_flat_list_returns_main_deck():
    raw = [{"name": "Sol Ring", "quantity": 1}]
    result = normalize_deck_input(raw)
    assert result["main_deck"] == raw
    assert result["commanders"] == []
    assert result["metadata"] == {}

def test_flat_list_empty():
    result = normalize_deck_input([])
    assert result["main_deck"] == []


# --- structured dict input ---

def test_structured_main_deck():
    raw = {"main_deck": [{"name": "Sol Ring", "quantity": 1}]}
    result = normalize_deck_input(raw)
    assert len(result["main_deck"]) == 1
    assert result["main_deck"][0]["name"] == "Sol Ring"

def test_structured_cards_alias():
    raw = {"cards": [{"name": "Arcane Signet", "quantity": 1}]}
    result = normalize_deck_input(raw)
    assert result["main_deck"][0]["name"] == "Arcane Signet"

def test_structured_single_commander():
    raw = {
        "commander": "Brago, King Eternal",
        "main_deck": [{"name": "Sol Ring", "quantity": 1}],
    }
    result = normalize_deck_input(raw)
    assert result["commanders"] == ["Brago, King Eternal"]

def test_structured_commanders_list():
    raw = {
        "commanders": ["Tymna the Weaver", "Thrasios, Triton Hero"],
        "main_deck": [{"name": "Sol Ring", "quantity": 1}],
    }
    result = normalize_deck_input(raw)
    assert "Tymna the Weaver" in result["commanders"]
    assert "Thrasios, Triton Hero" in result["commanders"]

def test_missing_main_deck_raises():
    with pytest.raises(ValueError, match="main_deck"):
        normalize_deck_input({"commander": "Brago, King Eternal"})

def test_unsupported_type_raises():
    with pytest.raises(ValueError):
        normalize_deck_input("not a deck")

def test_metadata_captures_extra_keys():
    raw = {
        "main_deck": [{"name": "Sol Ring"}],
        "theme": "blink",
        "bracket": "T3",
    }
    result = normalize_deck_input(raw)
    assert result["metadata"]["theme"] == "blink"
    assert result["metadata"]["bracket"] == "T3"

def test_commanders_key_not_in_metadata():
    raw = {
        "commanders": ["Brago, King Eternal"],
        "main_deck": [{"name": "Sol Ring"}],
    }
    result = normalize_deck_input(raw)
    assert "commanders" not in result["metadata"]
    assert "commander" not in result["metadata"]

def test_main_deck_not_in_metadata():
    raw = {"main_deck": [{"name": "Sol Ring"}]}
    result = normalize_deck_input(raw)
    assert "main_deck" not in result["metadata"]
