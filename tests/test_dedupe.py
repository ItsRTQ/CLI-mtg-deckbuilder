from mtgcli.cards.search import dedupe_cards

def test_dedupe_prefers_physical():
    cards = [
        {"name": "Sol Ring", "oracle_id": "1", "digital": True, "set_code": "vma"},
        {"name": "Sol Ring", "oracle_id": "1", "digital": False, "set_code": "znc"}
    ]
    deduped = dedupe_cards(cards)
    assert len(deduped) == 1
    assert deduped[0]["set_code"] == "znc"

def test_dedupe_prefers_set_info():
    cards = [
        {"name": "Sol Ring", "oracle_id": "1", "digital": False, "set_code": None},
        {"name": "Sol Ring", "oracle_id": "1", "digital": False, "set_code": "znc", "collector_number": "120"}
    ]
    deduped = dedupe_cards(cards)
    assert len(deduped) == 1
    assert deduped[0]["set_code"] == "znc"

def test_dedupe_prefers_price():
    cards = [
        {"name": "Sol Ring", "oracle_id": "1", "digital": False, "set_code": "znc", "usd_price": None},
        {"name": "Sol Ring", "oracle_id": "1", "digital": False, "set_code": "znc", "usd_price": "1.50"}
    ]
    deduped = dedupe_cards(cards)
    assert len(deduped) == 1
    assert deduped[0]["usd_price"] == "1.50"
