from mtgcli.validator.deck_validator import validate_commander_deck
from mtgcli.cards.repository import CardRepository
from mtgcli.config import SQLITE_PATH

def test_validate_deck_size_invalid():
    commander_name = "Chishiro, the Shattered Blade"
    repo = CardRepository(str(SQLITE_PATH))
    deck_entries = [
        {
            "quantity": 1,
            "name": "Chishiro, the Shattered Blade"
        },
        {
            "quantity": 1,
            "name": "Sol Ring"
        }
    ]
    result = validate_commander_deck(commander_name, deck_entries, repo)
    assert result["valid"] is False
    assert any(err["type"] == "deck_size" for err in result["errors"])
