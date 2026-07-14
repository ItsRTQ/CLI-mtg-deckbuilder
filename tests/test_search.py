from mtgcli.cards.search import search_commander_legal_cards, search_by_tags
from mtgcli.config import SQLITE_PATH


def test_search_no_printing_fields():
    results = search_commander_legal_cards(query="Sol Ring", limit=5)
    assert len(results) >= 1
    card = results[0]
    assert "set_code" not in card
    assert "collector_number" not in card
    assert "rarity" in card   # rarity became first-class (user request 2026-07-11)


def test_search_has_gameplay_fields():
    results = search_commander_legal_cards(query="Sol Ring", limit=5)
    assert len(results) >= 1
    card = results[0]
    assert "name" in card
    assert "mana_cost" in card
    assert "type_line" in card
    assert "oracle_text" in card
    assert "color_identity" in card
    assert "commander_legal" in card
    assert "can_be_commander" in card


def test_search_deduplicates():
    # Sol Ring has many printings; we should get exactly one result
    results = search_commander_legal_cards(query="Sol Ring", limit=50)
    names = [c["name"] for c in results]
    assert names.count("Sol Ring") == 1


def test_search_tags_no_printing_fields():
    results = search_by_tags(tags=["ramp"], limit=10)
    if results:
        card = results[0]
        assert "set_code" not in card
        assert "collector_number" not in card
        assert "rarity" in card   # rarity became first-class (user request 2026-07-11)
