from mtgcli.deckbuilder.suggestion_scorer import score_suggestion

def test_score_ramp_efficient():
    card = {
        "name": "Arcane Signet",
        "type_line": "Artifact",
        "oracle_text": "{T}: Add one mana of any color in your commander's color identity.",
        "mana_value": 2,
        "commander_legal": True
    }
    result = score_suggestion(card, "ramp")
    # Role match (+3), Efficiency (+2), Legality (+1) = 6
    assert result["score"] == 6
    assert "add one mana" in result["matched_tags"]

def test_score_theme_goblin():
    card = {
        "name": "Goblin Chieftain",
        "type_line": "Creature — Goblin",
        "oracle_text": "Haste. Other Goblin creatures you control get +1/+1 and have haste.",
        "mana_value": 3,
        "commander_legal": True
    }
    # Role: synergy (no tag match), Theme: goblins (+3), Legality (+1) = 4
    result = score_suggestion(card, "synergy", theme="goblins")
    assert result["score"] == 4
    assert "goblins" in result["matched_tags"]

def test_score_expensive_utility():
    card = {
        "name": "Expensive Removal",
        "type_line": "Instant",
        "oracle_text": "Destroy target creature.",
        "mana_value": 7,
        "commander_legal": True
    }
    # Role match (+3), High cost (-2), Legality (+1) = 2
    result = score_suggestion(card, "removal")
    assert result["score"] == 2

def test_score_no_text_penalty():
    card = {
        "name": "Vanilla Creature",
        "type_line": "Creature",
        "oracle_text": "",
        "mana_value": 2,
        "commander_legal": True
    }
    # Legality (+1), No text (-3) = -2 -> Capped at 1
    result = score_suggestion(card, "synergy")
    assert result["score"] == 1
    assert "Missing oracle text" in result["reason_hint"]
