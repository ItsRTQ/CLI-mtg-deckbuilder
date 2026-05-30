import pytest
from mtgcli.data.normalize_cards import parse_price, normalize_card, _price_status, min_known_price
from mtgcli.deckbuilder.pricing import resolve_card_price, build_budget_summary, evaluate_budget


# --- parse_price ---

def test_parse_price_string():
    assert parse_price("1.23") == 1.23

def test_parse_price_none():
    assert parse_price(None) is None

def test_parse_price_zero_string():
    assert parse_price("0.00") == 0.0

def test_parse_price_invalid():
    assert parse_price("N/A") is None

def test_parse_price_float():
    assert parse_price(2.5) == 2.5


# --- normalize_card price extraction ---

def _make_raw(prices: dict) -> dict:
    return {
        "oracle_id": "test-id",
        "name": "Test Card",
        "mana_cost": "{1}",
        "cmc": 1,
        "type_line": "Instant",
        "oracle_text": "",
        "colors": [],
        "color_identity": [],
        "legalities": {"commander": "legal"},
        "layout": "normal",
        "games": [],
        "digital": False,
        "finishes": [],
        "prices": prices,
    }

def test_normalize_extracts_usd():
    card = normalize_card(_make_raw({"usd": "1.50"}))
    assert card["usd_price"] == 1.50

def test_normalize_extracts_eur():
    card = normalize_card(_make_raw({"eur": "1.10"}))
    assert card["eur_price"] == 1.10

def test_normalize_extracts_all_price_fields():
    card = normalize_card(_make_raw({
        "usd": "1.00", "usd_foil": "2.00", "usd_etched": "3.00",
        "eur": "0.90", "eur_foil": "1.80", "tix": "0.05",
    }))
    assert card["usd_price"] == 1.00
    assert card["usd_foil_price"] == 2.00
    assert card["usd_etched_price"] == 3.00
    assert card["eur_price"] == 0.90
    assert card["eur_foil_price"] == 1.80
    assert card["tix_price"] == 0.05
    assert card["price_source"] == "scryfall"

def test_price_status_known_when_any_price():
    card = normalize_card(_make_raw({"usd": "1.00"}))
    assert card["price_status"] == "known"

def test_price_status_unknown_when_no_prices():
    card = normalize_card(_make_raw({}))
    assert card["price_status"] == "unknown"

def test_price_status_known_eur_only():
    card = normalize_card(_make_raw({"eur": "0.80"}))
    assert card["price_status"] == "known"

def test_normalize_null_prices_field():
    raw = _make_raw({})
    raw["prices"] = None
    card = normalize_card(raw)
    assert card["usd_price"] is None
    assert card["price_status"] == "unknown"


# --- resolve_card_price ---

def test_resolve_usd_known():
    card = {"usd_price": 1.23, "eur_price": None, "price_source": "scryfall"}
    result = resolve_card_price(card)
    assert result["price"] == 1.23
    assert result["currency"] == "USD"
    assert result["price_status"] == "known"

def test_resolve_usd_unknown_eur_known():
    card = {"usd_price": None, "eur_price": 1.10, "price_source": "scryfall"}
    result = resolve_card_price(card)
    assert result["price"] is None
    assert result["price_status"] == "unknown_usd_known_eur"
    assert result["eur_price"] == 1.10

def test_resolve_all_unknown():
    card = {"usd_price": None, "eur_price": None, "price_source": "scryfall"}
    result = resolve_card_price(card)
    assert result["price"] is None
    assert result["price_status"] == "unknown"

def test_resolve_unsupported_currency():
    card = {"usd_price": 1.0}
    with pytest.raises(ValueError):
        resolve_card_price(card, preferred_currency="jpy")


# --- build_budget_summary ---

def test_budget_summary_known_only():
    deck = [
        {"name": "Sol Ring", "quantity": 1, "usd_price": 1.50},
        {"name": "Command Tower", "quantity": 1, "usd_price": 0.25},
    ]
    summary = build_budget_summary(deck)
    assert summary["known_price_total"] == 1.75
    assert summary["known_price_cards_count"] == 2
    assert summary["unknown_price_cards_count"] == 0
    assert summary["budget_confidence"] == "complete"

def test_budget_summary_unknown_cards_partial():
    deck = [
        {"name": "Sol Ring", "quantity": 1, "usd_price": 1.50},
        {"name": "Mystery Card", "quantity": 1, "usd_price": None},
    ]
    summary = build_budget_summary(deck)
    assert summary["known_price_total"] == 1.50
    assert summary["unknown_price_cards_count"] == 1
    assert "Mystery Card" in summary["unknown_price_cards"]
    assert summary["budget_confidence"] == "partial"

def test_budget_summary_unknown_not_counted_as_zero():
    deck = [{"name": "Unknown Card", "quantity": 1, "usd_price": None}]
    summary = build_budget_summary(deck)
    assert summary["known_price_total"] == 0.0
    assert summary["unknown_price_cards_count"] == 1

def test_budget_summary_basics_treated_as_free():
    deck = [
        {"name": "Forest", "quantity": 10, "usd_price": None},
        {"name": "Sol Ring", "quantity": 1, "usd_price": 1.50},
    ]
    summary = build_budget_summary(deck, treat_basics_as_free=True)
    assert summary["known_price_total"] == 1.50
    assert summary["unknown_price_cards_count"] == 0
    assert summary["budget_confidence"] == "complete"

def test_budget_summary_complete_confidence_only_when_all_known():
    deck = [
        {"name": "Sol Ring", "quantity": 1, "usd_price": 1.50},
        {"name": "Arcane Signet", "quantity": 1, "usd_price": 0.75},
    ]
    summary = build_budget_summary(deck)
    assert summary["budget_confidence"] == "complete"


# --- min_known_price (aggregation helper) ---

def test_min_known_price_both_none():
    assert min_known_price(None, None) is None

def test_min_known_price_current_none():
    assert min_known_price(None, 2.0) == 2.0

def test_min_known_price_candidate_none():
    assert min_known_price(1.5, None) == 1.5

def test_min_known_price_takes_lower():
    assert min_known_price(3.0, 1.0) == 1.0

def test_min_known_price_equal():
    assert min_known_price(2.0, 2.0) == 2.0


# --- Price aggregation across printings (simulated) ---

def _make_printing(oracle_id: str, prices: dict) -> dict:
    """Makes a minimal raw Scryfall card dict."""
    return {
        "oracle_id": oracle_id,
        "name": "Test Card",
        "mana_cost": "{1}",
        "cmc": 1,
        "type_line": "Instant",
        "oracle_text": "",
        "colors": [],
        "color_identity": [],
        "legalities": {"commander": "legal"},
        "layout": "normal",
        "games": [],
        "digital": False,
        "finishes": [],
        "prices": prices,
    }


def _aggregate_printings(printings: list) -> dict:
    """Simulates build_sqlite aggregation logic for a list of raw printings."""
    from mtgcli.data.normalize_cards import normalize_card, min_known_price
    PRICE_FIELDS = ["usd_price", "usd_foil_price", "usd_etched_price", "eur_price", "eur_foil_price", "tix_price"]
    card_identities = {}
    for raw in printings:
        norm = normalize_card(raw)
        key = norm["oracle_id"]
        if key not in card_identities:
            card_identities[key] = norm
        else:
            existing = card_identities[key]
            for field in PRICE_FIELDS:
                existing[field] = min_known_price(existing[field], norm[field])
    # finalize
    for card in card_identities.values():
        any_known = any(card.get(f) is not None for f in PRICE_FIELDS)
        card["price_status"] = "known" if any_known else "unknown"
        card["price_source"] = "scryfall_aggregated_printings"
    return card_identities


def test_first_null_second_known_aggregates():
    """First printing has no price; second has USD price — result should be known."""
    printings = [
        _make_printing("abc", {}),
        _make_printing("abc", {"usd": "1.62"}),
    ]
    result = _aggregate_printings(printings)
    card = result["abc"]
    assert card["usd_price"] == 1.62
    assert card["price_status"] == "known"

def test_lowest_usd_wins():
    printings = [
        _make_printing("abc", {"usd": "3.00"}),
        _make_printing("abc", {"usd": "1.50"}),
        _make_printing("abc", {"usd": "2.00"}),
    ]
    result = _aggregate_printings(printings)
    assert result["abc"]["usd_price"] == 1.50

def test_lowest_eur_wins():
    printings = [
        _make_printing("abc", {"eur": "2.00"}),
        _make_printing("abc", {"eur": "0.80"}),
    ]
    result = _aggregate_printings(printings)
    assert result["abc"]["eur_price"] == 0.80

def test_all_null_printings_status_unknown():
    printings = [
        _make_printing("abc", {}),
        _make_printing("abc", {}),
    ]
    result = _aggregate_printings(printings)
    assert result["abc"]["price_status"] == "unknown"
    assert result["abc"]["usd_price"] is None

def test_mixed_printings_status_known():
    printings = [
        _make_printing("abc", {}),
        _make_printing("abc", {"eur": "1.00"}),
    ]
    result = _aggregate_printings(printings)
    assert result["abc"]["price_status"] == "known"

def test_duplicate_printings_collapse_to_one():
    printings = [
        _make_printing("abc", {"usd": "1.00"}),
        _make_printing("abc", {"usd": "2.00"}),
        _make_printing("abc", {"usd": "0.50"}),
    ]
    result = _aggregate_printings(printings)
    assert len(result) == 1

def test_different_oracle_ids_stay_separate():
    printings = [
        _make_printing("id1", {"usd": "1.00"}),
        _make_printing("id2", {"usd": "2.00"}),
    ]
    result = _aggregate_printings(printings)
    assert len(result) == 2

def test_price_source_is_aggregated():
    printings = [_make_printing("abc", {"usd": "1.00"})]
    result = _aggregate_printings(printings)
    assert result["abc"]["price_source"] == "scryfall_aggregated_printings"


# --- evaluate_budget ---

def test_under_budget():
    result = evaluate_budget(280.0, 500.0)
    assert result["budget_status"] == "under_budget"

def test_exactly_at_budget_is_under():
    result = evaluate_budget(500.0, 500.0)
    assert result["budget_status"] == "under_budget"

def test_within_overage_10pct():
    # $528 on a $500 budget = 5.6% over, within 10%
    result = evaluate_budget(528.0, 500.0, overage_percent=10)
    assert result["budget_status"] == "within_overage"

def test_at_hard_limit_is_within_overage():
    # $550 exactly = 10% over $500 → within_overage (not over)
    result = evaluate_budget(550.0, 500.0, overage_percent=10)
    assert result["budget_status"] == "within_overage"

def test_over_budget():
    # $551 on $500 → over hard limit of $550
    result = evaluate_budget(551.0, 500.0, overage_percent=10)
    assert result["budget_status"] == "over_budget"

def test_overage_0_strict():
    # $501 on $500 with 0% overage → over budget
    result = evaluate_budget(501.0, 500.0, overage_percent=0)
    assert result["budget_status"] == "over_budget"

def test_overage_0_exact_passes():
    result = evaluate_budget(500.0, 500.0, overage_percent=0)
    assert result["budget_status"] == "under_budget"

def test_hard_budget_limit_calculated():
    result = evaluate_budget(0, 500.0, overage_percent=10)
    assert result["hard_budget_limit"] == 550.0

def test_hard_budget_limit_with_0_overage():
    result = evaluate_budget(0, 200.0, overage_percent=0)
    assert result["hard_budget_limit"] == 200.0

def test_evaluate_budget_returns_note():
    result = evaluate_budget(280.0, 500.0)
    assert "note" in result
    assert len(result["note"]) > 0

def test_evaluate_budget_over_budget_note():
    result = evaluate_budget(612.0, 500.0)
    assert result["budget_status"] == "over_budget"
    assert "note" in result


# --- build_budget_summary with budget_limit ---

def test_summary_with_budget_limit_under():
    deck = [{"name": "Sol Ring", "quantity": 1, "usd_price": 1.50}]
    summary = build_budget_summary(deck, budget_limit=500.0)
    assert summary["budget_status"] == "under_budget"
    assert summary["budget_limit"] == 500.0
    assert summary["hard_budget_limit"] == 550.0

def test_summary_with_budget_limit_within_overage():
    # deck costs $528 on $500 budget
    deck = [{"name": "Expensive Card", "quantity": 1, "usd_price": 528.0}]
    summary = build_budget_summary(deck, budget_limit=500.0, overage_percent=10)
    assert summary["budget_status"] == "within_overage"

def test_summary_with_budget_limit_over():
    deck = [{"name": "Very Expensive Card", "quantity": 1, "usd_price": 612.0}]
    summary = build_budget_summary(deck, budget_limit=500.0)
    assert summary["budget_status"] == "over_budget"

def test_summary_without_budget_limit_has_no_status():
    deck = [{"name": "Sol Ring", "quantity": 1, "usd_price": 1.50}]
    summary = build_budget_summary(deck)
    assert "budget_status" not in summary

def test_under_budget_not_a_problem():
    # $280 deck on $500 budget is fine — budget_status under_budget, no error implied
    deck = [{"name": "Card", "quantity": 1, "usd_price": 280.0}]
    summary = build_budget_summary(deck, budget_limit=500.0)
    assert summary["budget_status"] == "under_budget"
    assert "note" in summary
    # note should not suggest spending more
    assert "target" in summary["note"].lower() or "maximum" in summary["note"].lower()

def test_partial_confidence_with_unknown_price_cards():
    deck = [
        {"name": "Sol Ring", "quantity": 1, "usd_price": 1.50},
        {"name": "Mystery", "quantity": 1, "usd_price": None},
    ]
    summary = build_budget_summary(deck, budget_limit=500.0)
    assert summary["budget_confidence"] == "partial"
    assert summary["budget_status"] == "under_budget"  # based on known total only

def test_overage_0_on_build_summary():
    deck = [{"name": "Sol Ring", "quantity": 1, "usd_price": 501.0}]
    summary = build_budget_summary(deck, budget_limit=500.0, overage_percent=0)
    assert summary["budget_status"] == "over_budget"

def test_overage_10_pct_budget_100():
    # $100 budget allows up to $110
    result = evaluate_budget(105.0, 100.0, overage_percent=10)
    assert result["budget_status"] == "within_overage"
    assert result["hard_budget_limit"] == 110.0

def test_overage_10_pct_budget_150():
    # $150 budget allows up to $165
    result = evaluate_budget(160.0, 150.0, overage_percent=10)
    assert result["budget_status"] == "within_overage"
    assert result["hard_budget_limit"] == 165.0
