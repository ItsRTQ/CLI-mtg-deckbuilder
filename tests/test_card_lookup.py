"""Human-readable output tests for `mtg card`.

These mock the repository and SQLite path so no real database is required.
"""
import pytest
from typer.testing import CliRunner

import mtgcli.cli as cli
import mtgcli.cli.commands.cards as card_cmd  # `card` command now lives here (cli.py split)
from mtgcli.cli import app, has_power_toughness

runner = CliRunner()


def _patch_card(monkeypatch, card):
    """Make `mtg card` resolve to a single mocked card dict."""
    class FakePath:
        def exists(self):
            return True

        def __str__(self):
            return ":memory:"

    monkeypatch.setattr(card_cmd, "SQLITE_PATH", FakePath())

    class FakeRepo:
        def __init__(self, *_args, **_kwargs):
            pass

        def get_card_by_exact_name(self, _name):
            return card

        def search_cards_by_name(self, *_a, **_k):
            return []

        def suggest_similar_names(self, *_a, **_k):
            return []

    monkeypatch.setattr(card_cmd, "CardRepository", FakeRepo)


EDGAR = {
    "name": "Edgar Markov",
    "mana_cost": "{3}{R}{W}{B}",
    "mana_value": 6.0,
    "type_line": "Legendary Creature — Vampire Knight",
    "oracle_text": "First strike, haste",
    "power": "4",
    "toughness": "4",
    "usd_price": None,
}

SOL_RING = {
    "name": "Sol Ring",
    "mana_cost": "{1}",
    "mana_value": 1.0,
    "type_line": "Artifact",
    "oracle_text": "{T}: Add {C}{C}.",
    "power": None,
    "toughness": None,
    "usd_price": None,
}


def test_has_power_toughness_helper():
    assert has_power_toughness({"power": "4", "toughness": "4"}) is True
    assert has_power_toughness({"power": "*", "toughness": None}) is True
    assert has_power_toughness({"power": None, "toughness": None}) is False
    assert has_power_toughness({}) is False


def test_creature_shows_power_toughness(monkeypatch):
    _patch_card(monkeypatch, EDGAR)
    res = runner.invoke(app, ["card", "Edgar Markov"])
    assert res.exit_code == 0
    assert "Power/Toughness: 4/4" in res.stdout


def test_non_creature_omits_power_toughness(monkeypatch):
    _patch_card(monkeypatch, SOL_RING)
    res = runner.invoke(app, ["card", "Sol Ring"])
    assert res.exit_code == 0
    assert "Power/Toughness" not in res.stdout


def test_non_numeric_pt_displays_without_crashing(monkeypatch):
    card = {**EDGAR, "name": "Tarmogoyf", "power": "*", "toughness": "1+*"}
    _patch_card(monkeypatch, card)
    res = runner.invoke(app, ["card", "Tarmogoyf"])
    assert res.exit_code == 0
    assert "Power/Toughness: */1+*" in res.stdout


def test_json_output_unchanged(monkeypatch):
    _patch_card(monkeypatch, EDGAR)
    res = runner.invoke(app, ["card", "Edgar Markov", "--json-output"])
    assert res.exit_code == 0
    assert '"power": "4"' in res.stdout
    assert '"toughness": "4"' in res.stdout
    # JSON view must not contain the human-readable label
    assert "Power/Toughness:" not in res.stdout


def test_existing_fields_preserved(monkeypatch):
    _patch_card(monkeypatch, EDGAR)
    res = runner.invoke(app, ["card", "Edgar Markov"])
    assert "Edgar Markov" in res.stdout
    assert "Legendary Creature — Vampire Knight" in res.stdout
    assert "First strike, haste" in res.stdout
