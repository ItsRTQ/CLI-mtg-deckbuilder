from mtgcli.cards.query_parser import parse_search_query, build_search_conditions, is_plain_query


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
