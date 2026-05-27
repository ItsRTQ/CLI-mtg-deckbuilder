from mtgcli.validator.deck_validator import validate_commander_deck

def test_validate_deck_size_invalid():
    commander_name = "Chishiro, the Shattered Blade"
    deck_cards = [
        {
            "quantity": 1,
            "name": "Chishiro, the Shattered Blade",
            "commander_legal": True,
            "color_identity": ["R", "G"]
        },
        {
            "quantity": 1,
            "name": "Sol Ring",
            "commander_legal": True,
            "color_identity": []
        }
    ]
    result = validate_commander_deck(commander_name, deck_cards)
    assert result["valid"] is False
    assert any(err["type"] == "deck_size" for err in result["errors"])
