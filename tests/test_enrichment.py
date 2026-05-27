import pytest
import json
from pathlib import Path
from mtgcli.deckbuilder.enrich_deck import enrich_deck
from mtgcli.config import SQLITE_PATH

def test_enrich_deck_basic(tmp_path):
    # This test depends on the database existing, which it does in this environment.
    deck_data = [
        {"name": "Sol Ring", "quantity": 1}
    ]
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

def test_enrich_deck_not_found(tmp_path):
    deck_data = [
        {"name": "This Card Does Not Exist", "quantity": 5}
    ]
    deck_path = tmp_path / "deck.json"
    deck_path.write_text(json.dumps(deck_data))
    
    output_path = tmp_path / "deck.enriched.json"
    
    result_path = enrich_deck(deck_path, SQLITE_PATH, output_path)
    
    enriched_data = json.loads(output_path.read_text())
    assert len(enriched_data) == 1
    assert enriched_data[0]["name"] == "This Card Does Not Exist"
    assert enriched_data[0]["quantity"] == 5

def test_enrich_deck_set_collector(tmp_path):
    # Arcane Signet from CMM should be found if it's in the DB
    # We saw earlier that Arcane Signet was found as CMM #653 by default
    deck_data = [
        {
            "name": "Arcane Signet", 
            "quantity": 1, 
            "set_code": "cmm", 
            "collector_number": "653"
        }
    ]
    deck_path = tmp_path / "deck.json"
    deck_path.write_text(json.dumps(deck_data))
    
    output_path = tmp_path / "deck.enriched.json"
    
    enrich_deck(deck_path, SQLITE_PATH, output_path)
    
    enriched_data = json.loads(output_path.read_text())
    assert enriched_data[0]["set_code"] == "cmm"
    assert str(enriched_data[0]["collector_number"]) == "653"
