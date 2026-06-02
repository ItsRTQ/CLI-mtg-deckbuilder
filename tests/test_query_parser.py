import pytest

from mtgcli.cards.query_parser import (
    parse_search_query,
    build_search_conditions,
    is_plain_query,
    check_query_conflicts,
    QueryConflictError,
)


# --- parse_search_query ---

def test_plain_free_text():
    result = parse_search_query("Demon")
    assert result["free_text"] == ["Demon"]
    assert result["type_terms"] == []
    assert result["oracle_terms"] == []

def test_type_token():
    result = parse_search_query("type:demon")
    assert result["type_terms"] == ["demon"]
    assert result["free_text"] == []

def test_type_token_case_insensitive():
    r1 = parse_search_query("type:Demon")
    r2 = parse_search_query("type:demon")
    # type_terms should both be lowercased
    assert r1["type_terms"] == r2["type_terms"]

def test_oracle_token():
    result = parse_search_query("oracle:draw")
    assert result["oracle_terms"] == ["draw"]

def test_text_alias_for_oracle():
    result = parse_search_query("text:draw")
    assert result["oracle_terms"] == ["draw"]

def test_name_token():
    result = parse_search_query("name:ring")
    assert result["name_terms"] == ["ring"]

def test_mv_exact():
    result = parse_search_query("mv:3")
    assert result["mana_value_eq"] == 3.0

def test_mv_lte():
    result = parse_search_query("mv<=2")
    assert result["mana_value_lte"] == 2.0

def test_mv_gte():
    result = parse_search_query("mv>=4")
    assert result["mana_value_gte"] == 4.0

def test_mixed_tokens():
    result = parse_search_query("type:creature oracle:draw mv<=3")
    assert result["type_terms"] == ["creature"]
    assert result["oracle_terms"] == ["draw"]
    assert result["mana_value_lte"] == 3.0
    assert result["free_text"] == []

def test_mixed_with_free_text():
    result = parse_search_query("type:demon sacrifice")
    assert result["type_terms"] == ["demon"]
    assert result["free_text"] == ["sacrifice"]

def test_multiple_free_text_words():
    result = parse_search_query("draw a card")
    assert result["free_text"] == ["draw", "a", "card"]

def test_empty_query():
    result = parse_search_query("")
    assert result["free_text"] == []
    assert result["type_terms"] == []

def test_mv_invalid_value_treated_as_free_text():
    result = parse_search_query("mv<=abc")
    assert "mv<=abc" in result["free_text"]

def test_unknown_token_treated_as_free_text():
    result = parse_search_query("color:red")
    assert "color:red" in result["free_text"]


# --- multiple / quoted structured tokens ---

def test_single_oracle_term():
    assert parse_search_query("oracle:draw")["oracle_terms"] == ["draw"]

def test_quoted_oracle_phrase_preserves_spaces():
    result = parse_search_query('oracle:"draw a card"')
    assert result["oracle_terms"] == ["draw a card"]

def test_multiple_oracle_terms_with_quotes_and_apostrophe():
    result = parse_search_query('''oracle:"can't be blocked" oracle:target oracle:creature''')
    assert result["oracle_terms"] == ["can't be blocked", "target", "creature"]

def test_text_alias_repeated_maps_to_oracle():
    result = parse_search_query("text:draw text:card")
    assert result["oracle_terms"] == ["draw", "card"]
    assert result["free_text"] == []

def test_repeated_type_terms():
    result = parse_search_query("type:vampire type:creature")
    assert result["type_terms"] == ["vampire", "creature"]

def test_name_and_type_terms():
    result = parse_search_query("name:Ajani type:planeswalker")
    assert result["name_terms"] == ["ajani"]
    assert result["type_terms"] == ["planeswalker"]

def test_both_mana_filters_and_oracle():
    result = parse_search_query("mv>=2 mv<=4 oracle:draw")
    assert result["mana_value_gte"] == 2.0
    assert result["mana_value_lte"] == 4.0
    assert result["oracle_terms"] == ["draw"]

def test_quoted_type_phrase():
    result = parse_search_query('type:"artifact creature"')
    assert result["type_terms"] == ["artifact creature"]


# --- check_query_conflicts ---

def test_conflict_impossible_range_raises():
    parsed = parse_search_query("mv<=2 mv>=5")
    with pytest.raises(QueryConflictError):
        check_query_conflicts(parsed)

def test_valid_range_no_conflict():
    parsed = parse_search_query("mv>=2 mv<=4 oracle:draw")
    check_query_conflicts(parsed)  # should not raise

def test_conflict_eq_outside_range_raises():
    parsed = parse_search_query("mv:5 mv<=2")
    with pytest.raises(QueryConflictError):
        check_query_conflicts(parsed)


# --- build_search_conditions ---

def test_type_condition_uses_type_line():
    parsed = parse_search_query("type:demon")
    conditions, params = build_search_conditions(parsed)
    assert any("type_line" in c for c in conditions)
    assert any("%demon%" in p for p in params)

def test_oracle_condition_uses_oracle_text():
    parsed = parse_search_query("oracle:draw")
    conditions, params = build_search_conditions(parsed)
    assert any("oracle_text" in c for c in conditions)
    assert any("%draw%" in p for p in params)

def test_name_condition_uses_name():
    parsed = parse_search_query("name:ring")
    conditions, params = build_search_conditions(parsed)
    assert any(c == "name LIKE ?" for c in conditions)
    assert "%ring%" in params

def test_free_text_matches_all_fields():
    parsed = parse_search_query("Demon")
    conditions, params = build_search_conditions(parsed)
    assert len(conditions) == 1
    assert "name LIKE ?" in conditions[0]
    assert "type_line LIKE ?" in conditions[0]
    assert "oracle_text LIKE ?" in conditions[0]

def test_mv_lte_condition():
    parsed = parse_search_query("mv<=2")
    conditions, params = build_search_conditions(parsed)
    assert "mana_value <= ?" in conditions
    assert 2.0 in params

def test_mv_gte_condition():
    parsed = parse_search_query("mv>=4")
    conditions, params = build_search_conditions(parsed)
    assert "mana_value >= ?" in conditions
    assert 4.0 in params

def test_multiple_conditions_are_separate():
    parsed = parse_search_query("type:creature oracle:draw")
    conditions, params = build_search_conditions(parsed)
    assert len(conditions) == 2

def test_multiple_oracle_terms_and_semantics():
    parsed = parse_search_query('''oracle:"can't be blocked" oracle:target oracle:creature''')
    conditions, params = build_search_conditions(parsed)
    # one condition per oracle term, all AND'd
    oracle_conds = [c for c in conditions if "oracle_text" in c]
    assert len(oracle_conds) == 3
    assert "%can't be blocked%" in params
    assert "%target%" in params
    assert "%creature%" in params

def test_params_are_parameterized_not_inlined():
    # values must travel as params (via ? placeholders), never inlined into SQL
    parsed = parse_search_query("oracle:dropcards")
    conditions, params = build_search_conditions(parsed)
    assert all("?" in c for c in conditions)
    assert all("dropcards" not in c for c in conditions)
    assert "%dropcards%" in params

def test_empty_query_produces_no_conditions():
    parsed = parse_search_query("")
    conditions, params = build_search_conditions(parsed)
    assert conditions == []
    assert params == []


# --- is_plain_query ---

def test_plain_query_is_plain():
    assert is_plain_query("Sol Ring") is True

def test_typed_query_is_not_plain():
    assert is_plain_query("type:demon") is False

def test_mv_query_is_not_plain():
    assert is_plain_query("mv<=2") is False
