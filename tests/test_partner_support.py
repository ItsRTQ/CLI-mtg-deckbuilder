import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from mtgcli.deckbuilder.skeleton_adjuster import get_main_deck_size
from mtgcli.validator.deck_validator import validate_commander_deck
from mtgcli.config import SQLITE_PATH, SEED_DATA_DIR


# --- skeleton commander_slots ---

def test_skeletons_use_commander_slots():
    skeleton_path = SEED_DATA_DIR / "deck_skeletons.json"
    skeletons = json.loads(skeleton_path.read_text())
    for name, skeleton in skeletons.items():
        assert "commander_slots" in skeleton, f"Skeleton '{name}' missing commander_slots"
        assert "commander" not in skeleton, f"Skeleton '{name}' still has old 'commander' key"


def test_skeleton_default_commander_slots_is_1():
    skeleton_path = SEED_DATA_DIR / "deck_skeletons.json"
    skeletons = json.loads(skeleton_path.read_text())
    for name, skeleton in skeletons.items():
        assert skeleton["commander_slots"] == 1, f"Skeleton '{name}' should default to 1"


def test_main_deck_size_single_commander():
    assert get_main_deck_size({"commander_slots": 1}) == 99


def test_main_deck_size_partner_commanders():
    assert get_main_deck_size({"commander_slots": 2}) == 98


def test_main_deck_size_default():
    assert get_main_deck_size({}) == 99


# --- validator: single commander ---

def _make_repo(cards_by_name: dict):
    """Creates a mock CardRepository returning cards from a dict."""
    repo = MagicMock()
    repo.get_card_by_exact_name.side_effect = lambda name: cards_by_name.get(name)
    return repo


def _make_card(name, can_be_commander=True, commander_legal=True, color_identity=None):
    return {
        "name": name,
        "can_be_commander": can_be_commander,
        "commander_legal": commander_legal,
        "color_identity": color_identity or [],
        "oracle_id": f"id-{name.lower().replace(' ', '-')}",
    }


def test_validator_single_commander_valid():
    from mtgcli.cards.repository import CardRepository
    repo = CardRepository(str(SQLITE_PATH))
    # Build minimal valid deck: commander + 99 cards
    commander_name = "Chishiro, the Shattered Blade"
    commander_card = repo.get_card_by_exact_name(commander_name)
    if not commander_card:
        pytest.skip("Commander not in DB")

    sol_ring = repo.get_card_by_exact_name("Sol Ring")
    if not sol_ring:
        pytest.skip("Sol Ring not in DB")

    # We just test deck_size error with 2-card deck
    deck_entries = [
        {"name": commander_name, "quantity": 1},
        {"name": "Sol Ring", "quantity": 1},
    ]
    result = validate_commander_deck(commander_name, deck_entries, repo)
    assert result["commander_slots"] == 1
    assert any(e["type"] == "invalid_deck_size" for e in result["errors"])


def test_validator_returns_commander_slots_field():
    cards = {
        "Commander A": _make_card("Commander A", color_identity=["W"]),
        "Sol Ring": _make_card("Sol Ring", can_be_commander=False, color_identity=[]),
    }
    repo = _make_repo(cards)
    deck = [{"name": "Commander A", "quantity": 1}, {"name": "Sol Ring", "quantity": 1}]
    result = validate_commander_deck("Commander A", deck, repo)
    assert "commander_slots" in result
    assert result["commander_slots"] == 1


def test_validator_returns_combined_color_identity():
    cards = {"Commander A": _make_card("Commander A", color_identity=["W", "B"])}
    repo = _make_repo(cards)
    deck = [{"name": "Commander A", "quantity": 1}]
    result = validate_commander_deck("Commander A", deck, repo)
    assert "combined_color_identity" in result
    assert set(result["combined_color_identity"]) == {"W", "B"}


# --- validator: partner commanders ---

def test_validator_partner_sets_commander_slots_2():
    cards = {
        "Commander A": _make_card("Commander A", color_identity=["W"]),
        "Commander B": _make_card("Commander B", color_identity=["G"]),
    }
    repo = _make_repo(cards)
    deck = [
        {"name": "Commander A", "quantity": 1},
        {"name": "Commander B", "quantity": 1},
    ]
    result = validate_commander_deck("Commander A", deck, repo, partner_name="Commander B")
    assert result["commander_slots"] == 2


def test_validator_partner_combines_color_identity():
    cards = {
        "Tymna": _make_card("Tymna", color_identity=["W", "B"]),
        "Thrasios": _make_card("Thrasios", color_identity=["G", "U"]),
    }
    repo = _make_repo(cards)
    deck = [{"name": "Tymna", "quantity": 1}, {"name": "Thrasios", "quantity": 1}]
    result = validate_commander_deck("Tymna", deck, repo, partner_name="Thrasios")
    assert set(result["combined_color_identity"]) == {"W", "B", "G", "U"}


def test_validator_partner_deck_100_cards_valid_size():
    """A partner deck with 100 cards (2 commanders + 98 main) should NOT trigger deck_size error."""
    all_cards = {}
    for i in range(98):
        name = f"Card {i}"
        all_cards[name] = _make_card(name, can_be_commander=False, color_identity=[])
    all_cards["Commander A"] = _make_card("Commander A", color_identity=[])
    all_cards["Commander B"] = _make_card("Commander B", color_identity=[])

    repo = _make_repo(all_cards)
    deck = [{"name": n, "quantity": 1} for n in all_cards]  # 100 total
    result = validate_commander_deck("Commander A", deck, repo, partner_name="Commander B")
    assert not any(e["type"] == "invalid_deck_size" for e in result["errors"]), result["errors"]


def test_validator_partner_deck_99_cards_fails_size():
    """A partner deck with only 99 cards should fail deck_size."""
    all_cards = {}
    for i in range(97):
        name = f"Card {i}"
        all_cards[name] = _make_card(name, can_be_commander=False, color_identity=[])
    all_cards["Commander A"] = _make_card("Commander A", color_identity=[])
    all_cards["Commander B"] = _make_card("Commander B", color_identity=[])

    repo = _make_repo(all_cards)
    deck = [{"name": n, "quantity": 1} for n in all_cards]  # 99 total
    result = validate_commander_deck("Commander A", deck, repo, partner_name="Commander B")
    assert any(e["type"] == "invalid_deck_size" for e in result["errors"])


def test_validator_partners_not_required_in_main_deck():
    """Partners supplied via CLI/metadata need not appear inside main_deck."""
    cards = {
        "Commander A": _make_card("Commander A", color_identity=["W"]),
        "Commander B": _make_card("Commander B", color_identity=["G"]),
    }
    filler = {
        f"Card {i}": _make_card(f"Card {i}", can_be_commander=False, color_identity=[])
        for i in range(98)
    }
    cards.update(filler)
    repo = _make_repo(cards)
    # Neither commander appears in the main deck — preferred structured shape.
    deck = [{"name": n, "quantity": 1} for n in filler.keys()]
    result = validate_commander_deck("Commander A", deck, repo, partner_name="Commander B")
    assert not any(e["type"] == "commander_missing" for e in result["errors"])
    assert result["expected_main_deck_size"] == 98
    assert result["actual_main_deck_size"] == 98
    assert result["valid"] is True


def test_validator_partner_color_identity_enforcement():
    """Card outside combined identity should be flagged."""
    cards = {
        "Commander A": _make_card("Commander A", color_identity=["W"]),
        "Commander B": _make_card("Commander B", color_identity=["G"]),
        "Blue Card": _make_card("Blue Card", can_be_commander=False, color_identity=["U"]),
    }
    repo = _make_repo(cards)
    deck = [
        {"name": "Commander A", "quantity": 1},
        {"name": "Commander B", "quantity": 1},
        {"name": "Blue Card", "quantity": 1},
    ]
    result = validate_commander_deck("Commander A", deck, repo, partner_name="Commander B")
    assert any(e["type"] == "color_identity_violation" and e["card"] == "Blue Card" for e in result["errors"])
