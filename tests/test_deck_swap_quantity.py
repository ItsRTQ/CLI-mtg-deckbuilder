import json
import pytest
from typer.testing import CliRunner

from mtgcli.cli import app
import mtgcli.cli.commands.deck as deck_mod


runner = CliRunner()


class FakeRepo:
    """Minimal repo: every card exists, is legal, and has colorless identity."""

    def get_card_by_exact_name(self, name):
        return {"name": name, "commander_legal": True, "color_identity": []}

    def suggest_similar_names(self, name, limit=3):
        return []


@pytest.fixture
def deck_file(tmp_path, monkeypatch):
    monkeypatch.setattr(deck_mod, "CardRepository", lambda *a, **k: FakeRepo())
    monkeypatch.setattr(deck_mod, "SQLITE_PATH", tmp_path / "db.sqlite")
    (tmp_path / "db.sqlite").write_text("")
    deck = {
        "commander": "Mendicant Core, Guidelight",
        "main_deck": [
            {"name": "Island", "quantity": 17},
            {"name": "Sol Ring", "quantity": 1},
        ],
    }
    path = tmp_path / "deck.json"
    path.write_text(json.dumps(deck))
    return path


def test_swap_from_basic_stack_takes_one_copy(deck_file):
    # The Mendicant build friction: "Island=Buried Ruin" must NOT rename all 17
    # Islands — it takes ONE copy out and adds the incoming card as its own entry.
    result = runner.invoke(app, [
        "deck-swap", "--deck", str(deck_file),
        "--commander", "Mendicant Core, Guidelight",
        "--swap", "Island=Buried Ruin",
    ])
    assert result.exit_code == 0, result.output
    deck = json.loads(deck_file.read_text())
    by = {e["name"]: e.get("quantity", 1) for e in deck["main_deck"]}
    assert by["Island"] == 16
    assert by["Buried Ruin"] == 1


def test_swap_singleton_entry_still_renames(deck_file):
    result = runner.invoke(app, [
        "deck-swap", "--deck", str(deck_file),
        "--commander", "Mendicant Core, Guidelight",
        "--swap", "Sol Ring=Mind Stone",
    ])
    assert result.exit_code == 0, result.output
    deck = json.loads(deck_file.read_text())
    names = [e["name"] for e in deck["main_deck"]]
    assert "Mind Stone" in names and "Sol Ring" not in names


def test_guard_rejects_nonbasic_quantity_over_one(deck_file):
    # If a non-basic somehow ends up with quantity > 1, the guard must abort.
    deck = json.loads(deck_file.read_text())
    deck["main_deck"].append({"name": "Buried Ruin", "quantity": 3})
    deck_file.write_text(json.dumps(deck))
    result = runner.invoke(app, [
        "deck-swap", "--deck", str(deck_file),
        "--commander", "Mendicant Core, Guidelight",
        "--swap", "Sol Ring=Mind Stone",
    ])
    assert result.exit_code == 1
    assert "singleton" in result.output.lower() or "duplicate" in result.output.lower()
