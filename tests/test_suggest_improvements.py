import json
from mtgcli.cards.search import dedupe_cards, search_by_tags
from mtgcli.deckbuilder.suggestion_scorer import score_suggestion
from mtgcli.utils.json_io import write_json
from pathlib import Path

def test_dedupe_removes_duplicates():
    cards = [
        {"name": "Sol Ring", "oracle_id": "1", "set_code": "a"},
        {"name": "Sol Ring", "oracle_id": "1", "set_code": "b"},
        {"name": "Llanowar Elves", "oracle_id": "2", "set_code": "c"}
    ]
    result = dedupe_cards(cards)
    assert len(result) == 2
    names = {c["name"] for c in result}
    assert "Sol Ring" in names
    assert "Llanowar Elves" in names

def test_price_filter_logic():
    # Note: search_by_tags uses the real SQLite DB. 
    # This test assumes the DB is built and contains cards with various prices.
    # We test the function directly.
    
    # Let's mock a bit or just verify the SQL injection part if possible, 
    # but since it's a black box, we'll check results if DB exists.
    results = search_by_tags(tags=["ramp"], max_price=0.5, limit=50)
    for card in results:
        if card["usd_price"] is not None:
            assert card["usd_price"] <= 0.5

def test_exclude_names_logic():
    # Test the exclusion logic in search_by_tags
    all_ramp = search_by_tags(tags=["ramp"], limit=10)
    if not all_ramp:
        return # Skip if no data
        
    excluded_name = all_ramp[0]["name"]
    filtered = search_by_tags(tags=["ramp"], exclude_names=[excluded_name], limit=10)
    
    for card in filtered:
        assert card["name"] != excluded_name

def test_scorer_goblin_theme():
    goblin_card = {
        "name": "Goblin Lackey",
        "type_line": "Creature — Goblin",
        "oracle_text": "Whenever Goblin Lackey deals damage...",
        "mana_value": 1,
        "commander_legal": True
    }
    non_goblin_card = {
        "name": "Llanowar Elves",
        "type_line": "Creature — Elf",
        "oracle_text": "{T}: Add {G}.",
        "mana_value": 1,
        "commander_legal": True
    }
    
    goblin_score = score_suggestion(goblin_card, "synergy", theme="goblins")
    non_goblin_score = score_suggestion(non_goblin_card, "synergy", theme="goblins")
    
    # Goblin should get +3 for theme, Elves should get 0 for theme.
    assert goblin_score["score"] > non_goblin_score["score"]
    assert "goblins" in goblin_score["matched_tags"]
    assert "goblins" not in non_goblin_score["matched_tags"]
