import pytest
import json
from pathlib import Path
from mtgcli.deckbuilder.enrich_deck import enrich_deck
from mtgcli.config import SQLITE_PATH


def test_enrich_deck_basic(tmp_path):
    deck_data = [{"name": "Sol Ring", "quantity": 1}]
    deck_path = tmp_path / "deck.json"
    deck_path.write_text(json.dumps(deck_data))
    output_path = tmp_path / "deck.enriched.json"

    result_path = enrich_deck(deck_path, SQLITE_PATH, output_path)

    assert result_path == output_path
    assert output_path.exists()

    enriched_data = json.loads(output_path.read_text())
    assert len(enriched_data) == 1
    assert enriched_data[0]["name"] == "Sol Ring"
    assert enriched_data[0]["quantity"] == 1
    assert "mana_cost" in enriched_data[0]
    assert isinstance(enriched_data[0]["colors"], list)
    assert "set_code" not in enriched_data[0]
    assert "rarity" in enriched_data[0]   # rarity became first-class (user request 2026-07-11)
    assert "collector_number" not in enriched_data[0]


def test_enrich_deck_not_found(tmp_path):
    deck_data = [{"name": "This Card Does Not Exist", "quantity": 5}]
    deck_path = tmp_path / "deck.json"
    deck_path.write_text(json.dumps(deck_data))
    output_path = tmp_path / "deck.enriched.json"

    result_path = enrich_deck(deck_path, SQLITE_PATH, output_path)

    enriched_data = json.loads(output_path.read_text())
    assert len(enriched_data) == 1
    assert enriched_data[0]["name"] == "This Card Does Not Exist"
    assert enriched_data[0]["quantity"] == 5


def test_enrich_deck_name_only_entry(tmp_path):
    # Deck entries with only name and quantity should be enriched correctly
    deck_data = [{"name": "Arcane Signet", "quantity": 1}]
    deck_path = tmp_path / "deck.json"
    deck_path.write_text(json.dumps(deck_data))
    output_path = tmp_path / "deck.enriched.json"

    enrich_deck(deck_path, SQLITE_PATH, output_path)

    enriched_data = json.loads(output_path.read_text())
    assert enriched_data[0]["name"] == "Arcane Signet"
    assert "oracle_id" in enriched_data[0]
    assert "set_code" not in enriched_data[0]
