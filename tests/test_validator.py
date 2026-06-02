import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from mtgcli.validator.deck_validator import validate_commander_deck


# --- Helpers ---

def make_repo(card_db: dict):
    repo = MagicMock()
    repo.get_card_by_exact_name.side_effect = lambda name: card_db.get(name)
    return repo


def make_card(name, color_identity=None, commander_legal=True, can_be_commander=False):
    return {
        "name": name,
        "color_identity": color_identity or [],
        "commander_legal": commander_legal,
        "can_be_commander": can_be_commander,
    }


def make_commander(name, color_identity=None, commander_legal=True):
    return make_card(name, color_identity=color_identity or [], commander_legal=commander_legal, can_be_commander=True)


def make_entry(name, quantity=1):
    return {"name": name, "quantity": quantity}


def _build_deck(commander_name, main_card_names, card_db):
    """Returns deck_entries with commander first, then main deck."""
    entries = [make_entry(commander_name)]
    for name in main_card_names:
        if isinstance(name, tuple):
            entries.append(make_entry(name[0], name[1]))
        else:
            entries.append(make_entry(name))
    return entries


def _colorless_cards(n, prefix="Card"):
    """Returns a dict of n colorless, legal, non-commander cards."""
    return {f"{prefix} {i}": make_card(f"{prefix} {i}", []) for i in range(n)}


def _valid_99_deck(commander, card_db=None):
    """Returns (deck_entries, card_db) for a valid single-commander 100-card deck."""
    db = {commander["name"]: commander}
    cards = _colorless_cards(99)
    db.update(cards)
    if card_db:
        db.update(card_db)
    entries = [make_entry(commander["name"])] + [make_entry(n) for n in cards]
    return entries, db


# --- Output shape ---

def test_output_has_required_fields():
    cmd = make_commander("Brago, King Eternal", ["W", "U"])
    entries, db = _valid_99_deck(cmd)
    repo = make_repo(db)
    result = validate_commander_deck("Brago, King Eternal", entries, repo)
    for field in ["valid", "commander", "partner", "commander_slots",
                  "expected_main_deck_size", "actual_main_deck_size",
                  "total_cards_including_commanders", "errors", "warnings",
                  "combined_color_identity"]:
        assert field in result, f"Missing field: {field}"


def test_valid_deck_output_shape():
    cmd = make_commander("Brago, King Eternal", ["W", "U"])
    entries, db = _valid_99_deck(cmd)
    repo = make_repo(db)
    result = validate_commander_deck("Brago, King Eternal", entries, repo)
    assert result["valid"] is True
    assert result["commander"] == "Brago, King Eternal"
    assert result["partner"] is None
    assert result["commander_slots"] == 1
    assert result["expected_main_deck_size"] == 99
    assert result["actual_main_deck_size"] == 99
    assert result["total_cards_including_commanders"] == 100
    assert result["errors"] == []
    # Legacy flat list includes the commander → treated as command-zone metadata.
    assert result["command_zone_cards_removed_from_main_deck"] == ["Brago, King Eternal"]
    assert any(w["type"] == "commander_in_main_deck" for w in result["warnings"])


# --- Card existence ---

def test_valid_card_names_pass():
    cmd = make_commander("Brago, King Eternal", ["W", "U"])
    entries, db = _valid_99_deck(cmd)
    repo = make_repo(db)
    result = validate_commander_deck("Brago, King Eternal", entries, repo)
    assert result["valid"] is True
    assert not any(e["type"] == "card_not_found" for e in result["errors"])


def test_misspelled_card_name_fails():
    cmd = make_commander("Brago, King Eternal", ["W", "U"])
    db = {cmd["name"]: cmd}
    # Build 98 valid cards + 1 misspelled
    db.update(_colorless_cards(98))
    entries = [make_entry(cmd["name"])] + [make_entry(n) for n in list(_colorless_cards(98).keys())] + [make_entry("Sole Ring")]
    repo = make_repo(db)
    result = validate_commander_deck("Brago, King Eternal", entries, repo)
    assert result["valid"] is False
    not_found = [e for e in result["errors"] if e["type"] == "card_not_found"]
    assert len(not_found) == 1
    assert not_found[0]["card"] == "Sole Ring"


def test_hallucinated_card_fails():
    cmd = make_commander("Brago, King Eternal", ["W", "U"])
    db = {cmd["name"]: cmd}
    db.update(_colorless_cards(98))
    entries = [make_entry(cmd["name"])] + [make_entry(n) for n in list(_colorless_cards(98).keys())] + [make_entry("Totally Fake Card XYZABC")]
    repo = make_repo(db)
    result = validate_commander_deck("Brago, King Eternal", entries, repo)
    assert result["valid"] is False
    assert any(e["type"] == "card_not_found" and e["card"] == "Totally Fake Card XYZABC" for e in result["errors"])


# --- Commander checks ---

def test_commander_not_found_fails():
    repo = make_repo({})
    result = validate_commander_deck("Nonexistent Commander", [], repo)
    assert result["valid"] is False
    assert any(e["type"] == "commander_not_found" for e in result["errors"])


def test_commander_not_eligible_fails():
    non_cmd = make_card("Sol Ring", [], commander_legal=True, can_be_commander=False)
    db = {"Sol Ring": non_cmd}
    repo = make_repo(db)
    result = validate_commander_deck("Sol Ring", [], repo)
    assert result["valid"] is False
    assert any(e["type"] == "invalid_commander" for e in result["errors"])


def test_commander_absent_from_main_deck_is_valid():
    """Structured style: commander supplied separately, not inside main_deck."""
    cmd = make_commander("Brago, King Eternal", ["W", "U"])
    db = {cmd["name"]: cmd}
    db.update(_colorless_cards(99))
    # Commander NOT in entries — this is the preferred structured shape.
    entries = [make_entry(n) for n in list(_colorless_cards(99).keys())]
    repo = make_repo(db)
    result = validate_commander_deck("Brago, King Eternal", entries, repo)
    assert result["valid"] is True
    assert not any(e["type"] == "commander_missing" for e in result["errors"])
    assert result["command_zone_cards_removed_from_main_deck"] == []
    assert result["actual_main_deck_size"] == 99
    assert result["total_cards_including_commanders"] == 100


# --- Commander legality ---

def test_not_commander_legal_fails():
    cmd = make_commander("Brago, King Eternal", ["W", "U"])
    banned_card = make_card("Black Lotus", [], commander_legal=False)
    db = {cmd["name"]: cmd, "Black Lotus": banned_card}
    db.update(_colorless_cards(98))
    entries = [make_entry(cmd["name"])] + [make_entry(n) for n in list(_colorless_cards(98).keys())] + [make_entry("Black Lotus")]
    repo = make_repo(db)
    result = validate_commander_deck("Brago, King Eternal", entries, repo)
    assert result["valid"] is False
    assert any(e["type"] == "not_commander_legal" and e["card"] == "Black Lotus" for e in result["errors"])


# --- Color identity ---

def test_color_identity_violation_fails():
    cmd = make_commander("Brago, King Eternal", ["W", "U"])
    black_card = make_card("Demonic Tutor", ["B"])
    db = {cmd["name"]: cmd, "Demonic Tutor": black_card}
    db.update(_colorless_cards(98))
    entries = [make_entry(cmd["name"])] + [make_entry(n) for n in list(_colorless_cards(98).keys())] + [make_entry("Demonic Tutor")]
    repo = make_repo(db)
    result = validate_commander_deck("Brago, King Eternal", entries, repo)
    assert result["valid"] is False
    violations = [e for e in result["errors"] if e["type"] == "color_identity_violation"]
    assert len(violations) == 1
    assert violations[0]["card"] == "Demonic Tutor"
    assert violations[0]["card_color_identity"] == ["B"]
    assert violations[0]["allowed_color_identity"] == ["U", "W"]


def test_colorless_card_passes_any_commander():
    cmd = make_commander("Chandra, Fire Artisan", ["R"])
    colorless_card = make_card("Sol Ring", [])
    db = {cmd["name"]: cmd, "Sol Ring": colorless_card}
    db.update(_colorless_cards(98))
    entries = [make_entry(cmd["name"])] + [make_entry(n) for n in list(_colorless_cards(98).keys())] + [make_entry("Sol Ring")]
    repo = make_repo(db)
    result = validate_commander_deck("Chandra, Fire Artisan", entries, repo)
    assert not any(e["type"] == "color_identity_violation" for e in result["errors"])


# --- Deck size ---

def test_99_main_plus_1_commander_is_valid():
    cmd = make_commander("Brago, King Eternal", ["W", "U"])
    entries, db = _valid_99_deck(cmd)
    repo = make_repo(db)
    result = validate_commander_deck("Brago, King Eternal", entries, repo)
    assert result["valid"] is True
    assert result["actual_main_deck_size"] == 99
    assert result["total_cards_including_commanders"] == 100
    assert not any(e["type"] == "invalid_deck_size" for e in result["errors"])


def test_100_main_plus_1_commander_fails():
    cmd = make_commander("Brago, King Eternal", ["W", "U"])
    db = {cmd["name"]: cmd}
    cards = _colorless_cards(100)
    db.update(cards)
    entries = [make_entry(cmd["name"])] + [make_entry(n) for n in cards]
    repo = make_repo(db)
    result = validate_commander_deck("Brago, King Eternal", entries, repo)
    assert result["valid"] is False
    size_errors = [e for e in result["errors"] if e["type"] == "invalid_deck_size"]
    assert len(size_errors) == 1
    assert size_errors[0]["actual_main_deck_size"] == 100
    assert size_errors[0]["expected_main_deck_size"] == 99


def test_deck_size_counts_quantities():
    cmd = make_commander("Brago, King Eternal", ["W", "U"])
    db = {cmd["name"]: cmd}
    db["Plains"] = make_card("Plains", [])
    # Only 1 entry but quantity=10, rest are 89 single cards
    other_cards = _colorless_cards(89)
    db.update(other_cards)
    entries = [make_entry(cmd["name"]), make_entry("Plains", 10)] + [make_entry(n) for n in other_cards]
    repo = make_repo(db)
    result = validate_commander_deck("Brago, King Eternal", entries, repo)
    assert result["actual_main_deck_size"] == 99  # 10 + 89


# --- Partner decks ---

def test_98_main_plus_2_commanders_is_valid():
    cmd1 = make_commander("Tymna the Weaver", ["W", "B"])
    cmd2 = make_commander("Thrasios, Triton Hero", ["G", "U"])
    db = {cmd1["name"]: cmd1, cmd2["name"]: cmd2}
    cards = _colorless_cards(98)
    db.update(cards)
    entries = [make_entry(cmd1["name"]), make_entry(cmd2["name"])] + [make_entry(n) for n in cards]
    repo = make_repo(db)
    result = validate_commander_deck("Tymna the Weaver", entries, repo, partner_name="Thrasios, Triton Hero")
    assert result["valid"] is True
    assert result["commander_slots"] == 2
    assert result["expected_main_deck_size"] == 98
    assert result["actual_main_deck_size"] == 98
    assert result["total_cards_including_commanders"] == 100


def test_99_main_plus_2_commanders_fails():
    cmd1 = make_commander("Tymna the Weaver", ["W", "B"])
    cmd2 = make_commander("Thrasios, Triton Hero", ["G", "U"])
    db = {cmd1["name"]: cmd1, cmd2["name"]: cmd2}
    cards = _colorless_cards(99)
    db.update(cards)
    entries = [make_entry(cmd1["name"]), make_entry(cmd2["name"])] + [make_entry(n) for n in cards]
    repo = make_repo(db)
    result = validate_commander_deck("Tymna the Weaver", entries, repo, partner_name="Thrasios, Triton Hero")
    assert result["valid"] is False
    size_errors = [e for e in result["errors"] if e["type"] == "invalid_deck_size"]
    assert len(size_errors) == 1
    assert size_errors[0]["expected_main_deck_size"] == 98
    assert size_errors[0]["actual_main_deck_size"] == 99


def test_partner_combined_color_identity():
    cmd1 = make_commander("Tymna the Weaver", ["W", "B"])
    cmd2 = make_commander("Thrasios, Triton Hero", ["G", "U"])
    db = {cmd1["name"]: cmd1, cmd2["name"]: cmd2}
    cards = _colorless_cards(98)
    db.update(cards)
    entries = [make_entry(cmd1["name"]), make_entry(cmd2["name"])] + [make_entry(n) for n in cards]
    repo = make_repo(db)
    result = validate_commander_deck("Tymna the Weaver", entries, repo, partner_name="Thrasios, Triton Hero")
    assert set(result["combined_color_identity"]) == {"W", "B", "G", "U"}


def test_partner_color_identity_violation():
    cmd1 = make_commander("Tymna the Weaver", ["W", "B"])
    cmd2 = make_commander("Thrasios, Triton Hero", ["G", "U"])
    red_card = make_card("Lightning Bolt", ["R"])
    db = {cmd1["name"]: cmd1, cmd2["name"]: cmd2, "Lightning Bolt": red_card}
    cards = _colorless_cards(97)
    db.update(cards)
    entries = (
        [make_entry(cmd1["name"]), make_entry(cmd2["name"])]
        + [make_entry(n) for n in cards]
        + [make_entry("Lightning Bolt")]
    )
    repo = make_repo(db)
    result = validate_commander_deck("Tymna the Weaver", entries, repo, partner_name="Thrasios, Triton Hero")
    assert any(
        e["type"] == "color_identity_violation" and e["card"] == "Lightning Bolt"
        for e in result["errors"]
    )


# --- Singleton rule ---

def test_non_basic_duplicate_fails():
    cmd = make_commander("Brago, King Eternal", ["W", "U"])
    db = {cmd["name"]: cmd, "Sol Ring": make_card("Sol Ring", [])}
    db.update(_colorless_cards(97))
    entries = (
        [make_entry(cmd["name"])]
        + [make_entry(n) for n in list(_colorless_cards(97).keys())]
        + [make_entry("Sol Ring", 2)]
    )
    repo = make_repo(db)
    result = validate_commander_deck("Brago, King Eternal", entries, repo)
    assert result["valid"] is False
    assert any(e["type"] == "singleton_violation" and e["card"] == "Sol Ring" for e in result["errors"])


def test_basic_land_quantity_greater_than_1_passes():
    cmd = make_commander("Brago, King Eternal", ["W", "U"])
    db = {cmd["name"]: cmd, "Island": make_card("Island", [])}
    db.update(_colorless_cards(89))
    entries = (
        [make_entry(cmd["name"])]
        + [make_entry(n) for n in list(_colorless_cards(89).keys())]
        + [make_entry("Island", 10)]
    )
    repo = make_repo(db)
    result = validate_commander_deck("Brago, King Eternal", entries, repo)
    assert not any(e["type"] == "singleton_violation" for e in result["errors"])
    assert result["actual_main_deck_size"] == 99


def test_all_basic_land_types_allowed_multiple():
    for land in ["Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"]:
        cmd = make_commander("Test Commander", [])
        db = {cmd["name"]: cmd, land: make_card(land, [])}
        db.update(_colorless_cards(89))
        entries = (
            [make_entry(cmd["name"])]
            + [make_entry(n) for n in list(_colorless_cards(89).keys())]
            + [make_entry(land, 10)]
        )
        repo = make_repo(db)
        result = validate_commander_deck("Test Commander", entries, repo)
        assert not any(e["type"] == "singleton_violation" for e in result["errors"]), f"Failed for {land}"


# --- Error type names (spec compliance) ---

def test_error_type_card_not_found():
    cmd = make_commander("Brago, King Eternal", ["W", "U"])
    db = {cmd["name"]: cmd}
    db.update(_colorless_cards(98))
    entries = [make_entry(cmd["name"])] + [make_entry(n) for n in list(_colorless_cards(98).keys())] + [make_entry("Ghost Card")]
    repo = make_repo(db)
    result = validate_commander_deck("Brago, King Eternal", entries, repo)
    assert any(e["type"] == "card_not_found" for e in result["errors"])


def test_error_type_not_commander_legal():
    cmd = make_commander("Brago, King Eternal", ["W", "U"])
    illegal = make_card("Banned Card", [], commander_legal=False)
    db = {cmd["name"]: cmd, "Banned Card": illegal}
    db.update(_colorless_cards(98))
    entries = [make_entry(cmd["name"])] + [make_entry(n) for n in list(_colorless_cards(98).keys())] + [make_entry("Banned Card")]
    repo = make_repo(db)
    result = validate_commander_deck("Brago, King Eternal", entries, repo)
    assert any(e["type"] == "not_commander_legal" for e in result["errors"])


def test_error_type_color_identity_violation():
    cmd = make_commander("Brago, King Eternal", ["W", "U"])
    black = make_card("Dark Card", ["B"])
    db = {cmd["name"]: cmd, "Dark Card": black}
    db.update(_colorless_cards(98))
    entries = [make_entry(cmd["name"])] + [make_entry(n) for n in list(_colorless_cards(98).keys())] + [make_entry("Dark Card")]
    repo = make_repo(db)
    result = validate_commander_deck("Brago, King Eternal", entries, repo)
    assert any(e["type"] == "color_identity_violation" for e in result["errors"])


def test_error_type_invalid_deck_size():
    cmd = make_commander("Brago, King Eternal", ["W", "U"])
    db = {cmd["name"]: cmd}
    entries = [make_entry(cmd["name"])]  # only commander, 0 main deck
    repo = make_repo(db)
    result = validate_commander_deck("Brago, King Eternal", entries, repo)
    assert any(e["type"] == "invalid_deck_size" for e in result["errors"])


def test_color_identity_error_has_identity_fields():
    cmd = make_commander("Brago, King Eternal", ["W", "U"])
    black = make_card("Demonic Tutor", ["B"])
    db = {cmd["name"]: cmd, "Demonic Tutor": black}
    db.update(_colorless_cards(98))
    entries = [make_entry(cmd["name"])] + [make_entry(n) for n in list(_colorless_cards(98).keys())] + [make_entry("Demonic Tutor")]
    repo = make_repo(db)
    result = validate_commander_deck("Brago, King Eternal", entries, repo)
    err = next(e for e in result["errors"] if e["type"] == "color_identity_violation")
    assert "card_color_identity" in err
    assert "allowed_color_identity" in err


# --- Multiple errors in one deck ---

def test_multiple_errors_collected():
    cmd = make_commander("Brago, King Eternal", ["W", "U"])
    illegal = make_card("Banned", [], commander_legal=False)
    black = make_card("Dark Ritual", ["B"])
    db = {cmd["name"]: cmd, "Banned": illegal, "Dark Ritual": black}
    db.update(_colorless_cards(97))
    entries = (
        [make_entry(cmd["name"])]
        + [make_entry(n) for n in list(_colorless_cards(97).keys())]
        + [make_entry("Banned"), make_entry("Dark Ritual")]
        # Note: 97+2=99 main deck cards, so size is fine
    )
    repo = make_repo(db)
    result = validate_commander_deck("Brago, King Eternal", entries, repo)
    assert result["valid"] is False
    types = {e["type"] for e in result["errors"]}
    assert "not_commander_legal" in types
    assert "color_identity_violation" in types


# --- Integration test with real DB (requires mtg init-data) ---

def test_validate_deck_size_invalid_real_db():
    try:
        from mtgcli.cards.repository import CardRepository
        from mtgcli.config import SQLITE_PATH
        if not SQLITE_PATH.exists():
            pytest.skip("SQLite database not found. Run 'mtg init-data' first.")
        repo = CardRepository(str(SQLITE_PATH))
        deck_entries = [
            {"quantity": 1, "name": "Chishiro, the Shattered Blade"},
            {"quantity": 1, "name": "Sol Ring"},
        ]
        result = validate_commander_deck("Chishiro, the Shattered Blade", deck_entries, repo)
        assert result["valid"] is False
        assert any(e["type"] == "invalid_deck_size" for e in result["errors"])
    except ImportError:
        pytest.skip("mtgcli not installed")
