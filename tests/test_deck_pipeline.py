"""
End-to-end alignment tests for deck-write → deck-fill-lands → validate.

These three commands must agree on command-zone handling: the commander lives
outside main_deck, and a deck produced by one command must validate via the
next without manual fixups (no commander_missing).

Uses the real card DB (skipped if unavailable).
"""
import json
import pytest
from typer.testing import CliRunner

from mtgcli.config import SQLITE_PATH
from mtgcli.cli import app
from mtgcli.validator.deck_validator import validate_commander_deck
from mtgcli.cards.repository import CardRepository

pytestmark = pytest.mark.skipif(not SQLITE_PATH.exists(), reason="card DB not built")

KOTIS = "Kotis, the Fangkeeper"
runner = CliRunner()


def test_deck_write_structured_excludes_commander_from_main_deck(tmp_path):
    txt = tmp_path / "decklist.txt"
    txt.write_text(f"1 {KOTIS}\n1 Sol Ring\n1 Arcane Signet\n")
    out = tmp_path / "deck.json"
    res = runner.invoke(app, [
        "deck-write", "--input", str(txt), "--output", str(out),
        "--commander", KOTIS, "--structured", "--force", "--json-output",
    ])
    assert res.exit_code == 0, res.output
    data = json.loads(out.read_text())
    assert data["commander"] == KOTIS
    names = [e["name"] for e in data["main_deck"]]
    assert KOTIS not in names
    assert "Sol Ring" in names


def test_full_pipeline_validates_without_commander_missing(tmp_path):
    txt = tmp_path / "decklist.txt"
    txt.write_text(f"1 {KOTIS}\n1 Sol Ring\n1 Arcane Signet\n")
    deck = tmp_path / "deck.json"

    r1 = runner.invoke(app, [
        "deck-write", "--input", str(txt), "--output", str(deck),
        "--commander", KOTIS, "--structured", "--force", "--json-output",
    ])
    assert r1.exit_code == 0, r1.output

    r2 = runner.invoke(app, [
        "deck-fill-lands", "--deck", str(deck), "--commander", KOTIS,
        "--output", str(deck), "--force", "--json-output",
    ])
    assert r2.exit_code == 0, r2.output

    # Structured shape preserved through fill-lands.
    filled = json.loads(deck.read_text())
    assert isinstance(filled, dict)
    assert filled["commander"] == KOTIS
    assert KOTIS not in [e["name"] for e in filled["main_deck"]]

    r3 = runner.invoke(app, [
        "validate", "--commander", KOTIS, "--deck", str(deck), "--json-output",
    ])
    assert r3.exit_code == 0, r3.output
    report = json.loads(r3.output)
    assert not any(e["type"] == "commander_missing" for e in report["errors"])
    assert report["expected_main_deck_size"] == 99
    assert report["actual_main_deck_size"] == 99
    assert report["total_cards_including_commanders"] == 100
    assert report["valid"] is True


def test_validate_uses_structured_commander_metadata(tmp_path):
    """validate falls back to deck metadata when --commander is omitted."""
    repo = CardRepository(str(SQLITE_PATH))
    kotis = repo.get_card_by_exact_name(KOTIS)
    identity = kotis["color_identity"]
    # Build a structured 99-card deck (Sol Ring + 98 basics in identity).
    basics_for = {"W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest"}
    basic = basics_for[identity[0]]
    deck = {
        "commander": KOTIS,
        "main_deck": [
            {"name": "Sol Ring", "quantity": 1},
            {"name": basic, "quantity": 98},
        ],
    }
    deck_path = tmp_path / "deck.json"
    deck_path.write_text(json.dumps(deck))

    res = runner.invoke(app, ["validate", "--deck", str(deck_path), "--json-output"])
    assert res.exit_code == 0, res.output
    report = json.loads(res.output)
    assert report["commander"] == KOTIS
    assert not any(e["type"] == "commander_missing" for e in report["errors"])
    assert report["actual_main_deck_size"] == 99


def test_flat_list_with_commander_validates_via_cli_flag(tmp_path):
    """Legacy flat list containing the commander validates with --commander."""
    repo = CardRepository(str(SQLITE_PATH))
    kotis = repo.get_card_by_exact_name(KOTIS)
    basic = {"W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest"}[
        kotis["color_identity"][0]
    ]
    flat = [
        {"name": KOTIS, "quantity": 1},
        {"name": "Sol Ring", "quantity": 1},
        {"name": basic, "quantity": 98},
    ]
    deck_path = tmp_path / "deck.json"
    deck_path.write_text(json.dumps(flat))

    res = runner.invoke(app, [
        "validate", "--commander", KOTIS, "--deck", str(deck_path), "--json-output",
    ])
    assert res.exit_code == 0, res.output
    report = json.loads(res.output)
    assert report["command_zone_cards_removed_from_main_deck"] == [KOTIS]
    assert report["actual_main_deck_size"] == 99
    assert not any(e["type"] == "commander_missing" for e in report["errors"])
    assert report["valid"] is True


def test_partner_structured_deck_validates_with_98(tmp_path):
    """Partner deck: 98-card main deck, neither commander inside main_deck."""
    c1, c2 = "Tymna the Weaver", "Thrasios, Triton Hero"
    # Combined identity W/B/G/U → use Island filler (U in both via Thrasios).
    deck = {
        "commanders": [c1, c2],
        "main_deck": [
            {"name": "Sol Ring", "quantity": 1},
            {"name": "Island", "quantity": 97},
        ],
    }
    deck_path = tmp_path / "deck.json"
    deck_path.write_text(json.dumps(deck))

    res = runner.invoke(app, [
        "validate", "--commander", c1, "--partner", c2,
        "--deck", str(deck_path), "--json-output",
    ])
    assert res.exit_code == 0, res.output
    report = json.loads(res.output)
    assert report["expected_main_deck_size"] == 98
    assert report["actual_main_deck_size"] == 98
    assert report["total_cards_including_commanders"] == 100
    assert not any(e["type"] == "commander_missing" for e in report["errors"])
    assert report["valid"] is True
