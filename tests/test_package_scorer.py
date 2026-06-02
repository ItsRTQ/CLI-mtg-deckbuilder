from mtgcli.deckbuilder.package_scorer import score_package_card


def test_token_maker_scores_for_token_engine():
    card = {
        "name": "Raise the Alarm",
        "type_line": "Instant",
        "oracle_text": "Create two 1/1 white Soldier creature tokens.",
        "mana_value": 2
    }
    result = score_package_card(card, "token_engine", "token_makers")
    assert result["suggestion_score"] >= 3
    assert len(result["matched_tags"]) > 0


def test_death_trigger_scores_for_sacrifice_value():
    card = {
        "name": "Blood Artist",
        "type_line": "Creature — Vampire",
        "oracle_text": "Whenever Blood Artist or another creature dies, target player loses 1 life and you gain 1 life.",
        "mana_value": 2
    }
    result = score_package_card(card, "sacrifice_value", "death_payoffs")
    assert result["suggestion_score"] >= 3
    assert len(result["matched_tags"]) > 0


def test_etb_value_scores_for_etb_blink():
    card = {
        "name": "Cloudblazer",
        "type_line": "Creature — Human Scout",
        "oracle_text": "Flying. When Cloudblazer enters the battlefield, you gain 2 life and draw 2 cards.",
        "mana_value": 5
    }
    result = score_package_card(card, "etb_blink_engine", "etb_value")
    assert result["suggestion_score"] >= 3


def test_unknown_theme_returns_base_score():
    card = {
        "name": "Generic Card",
        "type_line": "Creature",
        "oracle_text": "Flying",
        "mana_value": 3
    }
    result = score_package_card(card, "nonexistent_theme", "some_package")
    assert result["suggestion_score"] >= 1
    assert "suggestion_score" in result
    assert "matched_tags" in result
    assert "reason_hint" in result


def test_mana_efficiency_bonus():
    cheap_card = {
        "name": "Cheap Card",
        "type_line": "Creature",
        "oracle_text": "creature token",
        "mana_value": 2
    }
    expensive_card = {
        "name": "Expensive Card",
        "type_line": "Creature",
        "oracle_text": "creature token",
        "mana_value": 7
    }
    cheap_result = score_package_card(cheap_card, "token_engine", "token_makers")
    expensive_result = score_package_card(expensive_card, "token_engine", "token_makers")
    assert cheap_result["suggestion_score"] > expensive_result["suggestion_score"]
