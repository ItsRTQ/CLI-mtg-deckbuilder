from mtgcli.deckbuilder.package_scorer import score_package_card


def test_equipment_scores_for_modified_enablers():
    card = {
        "name": "Test Equipment",
        "type_line": "Artifact — Equipment",
        "oracle_text": "Equipped creature gets +1/+1.",
        "mana_value": 2
    }

    result = score_package_card(card, "modified_creatures", "modified_enablers")

    assert result["suggestion_score"] >= 5
    assert "equipment" in result["matched_tags"]


def test_goblin_scores_for_goblin_theme():
    card = {
        "name": "Test Goblin",
        "type_line": "Creature — Goblin",
        "oracle_text": "Other Goblins you control get +1/+1.",
        "mana_value": 2
    }

    result = score_package_card(card, "goblins", "goblin_payoffs")

    assert result["suggestion_score"] >= 5
    assert "goblin" in result["matched_tags"]
