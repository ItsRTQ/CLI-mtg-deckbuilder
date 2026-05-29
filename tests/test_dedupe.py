from mtgcli.cards.search import dedupe_cards


def test_dedupe_by_oracle_id():
    cards = [
        {"name": "Sol Ring", "oracle_id": "abc-123", "digital": False},
        {"name": "Sol Ring", "oracle_id": "abc-123", "digital": False},
    ]
    deduped = dedupe_cards(cards)
    assert len(deduped) == 1


def test_dedupe_prefers_physical():
    cards = [
        {"name": "Sol Ring", "oracle_id": "abc-123", "digital": True},
        {"name": "Sol Ring", "oracle_id": "abc-123", "digital": False},
    ]
    deduped = dedupe_cards(cards)
    assert len(deduped) == 1
    assert deduped[0]["digital"] is False


def test_dedupe_different_cards():
    cards = [
        {"name": "Sol Ring", "oracle_id": "abc-123", "digital": False},
        {"name": "Arcane Signet", "oracle_id": "def-456", "digital": False},
    ]
    deduped = dedupe_cards(cards)
    assert len(deduped) == 2


def test_dedupe_fallback_to_name():
    cards = [
        {"name": "Sol Ring", "oracle_id": None, "digital": False},
        {"name": "Sol Ring", "oracle_id": None, "digital": False},
    ]
    deduped = dedupe_cards(cards)
    assert len(deduped) == 1
