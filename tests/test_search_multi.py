"""
Integration tests for multi-token AND search semantics.

Builds a tiny temp SQLite DB so inclusion/exclusion can be asserted exactly,
independent of the real card database.
"""
import json
import sqlite3

import pytest

import mtgcli.cards.search as search_mod
from mtgcli.cards.search import search_commander_legal_cards


_COLUMNS = [
    "oracle_id", "name", "mana_cost", "mana_value", "type_line", "oracle_text",
    "colors", "color_identity", "games", "finishes",
    "commander_legal", "can_be_commander", "digital", "usd_price",
    "power", "toughness",
]


def _make_card(oracle_id, name, type_line, oracle_text, mana_value=2.0):
    return {
        "oracle_id": oracle_id,
        "name": name,
        "mana_cost": "{1}{U}",
        "mana_value": mana_value,
        "type_line": type_line,
        "oracle_text": oracle_text,
        "colors": json.dumps(["U"]),
        "color_identity": json.dumps(["U"]),
        "games": json.dumps(["paper"]),
        "finishes": json.dumps(["nonfoil"]),
        "commander_legal": 1,
        "can_be_commander": 0,
        "digital": 0,
        "usd_price": None,
        "power": None,
        "toughness": None,
    }


@pytest.fixture
def fixture_db(tmp_path, monkeypatch):
    db_path = tmp_path / "cards.db"
    conn = sqlite3.connect(str(db_path))
    cols_ddl = ", ".join(f"{c} TEXT" for c in _COLUMNS)
    conn.execute(f"CREATE TABLE cards ({cols_ddl})")

    cards = [
        _make_card("a", "Card A", "Creature — Human", "Target creature can't be blocked this turn."),
        _make_card("b", "Card B", "Creature — Human", "Target creature gets +2/+2 until end of turn."),
        _make_card("c", "Card C", "Creature — Human", "This creature can't be blocked.", mana_value=5.0),
    ]
    for card in cards:
        placeholders = ", ".join("?" for _ in _COLUMNS)
        conn.execute(
            f"INSERT INTO cards ({', '.join(_COLUMNS)}) VALUES ({placeholders})",
            [card[c] for c in _COLUMNS],
        )
    conn.commit()
    conn.close()

    class FakePath:
        def exists(self):
            return True

        def __str__(self):
            return str(db_path)

    monkeypatch.setattr(search_mod, "SQLITE_PATH", FakePath())
    import mtgcli.cli.commands.search as cli_mod  # `search` command now lives here (cli.py split)
    monkeypatch.setattr(cli_mod, "SQLITE_PATH", FakePath())
    return db_path


def _names(results):
    return {c["name"] for c in results}


def test_three_oracle_terms_and_only_card_a(fixture_db):
    results = search_commander_legal_cards(
        query='''oracle:"can't be blocked" oracle:target oracle:creature'''
    )
    assert _names(results) == {"Card A"}


def test_single_oracle_term_matches_more(fixture_db):
    results = search_commander_legal_cards(query="oracle:creature")
    assert _names(results) == {"Card A", "Card B", "Card C"}


def test_card_matching_only_one_term_excluded(fixture_db):
    # "target" alone excludes Card C (no "target")
    results = search_commander_legal_cards(query="oracle:target")
    assert _names(results) == {"Card A", "Card B"}


def test_repeated_type_terms_and(fixture_db):
    # both terms present in every type_line → all match
    results = search_commander_legal_cards(query="type:creature type:human")
    assert _names(results) == {"Card A", "Card B", "Card C"}
    # a type term that no card has → empty
    results = search_commander_legal_cards(query="type:creature type:artifact")
    assert _names(results) == set()


def test_quoted_phrase_with_spaces(fixture_db):
    results = search_commander_legal_cards(query='oracle:"can\'t be blocked"')
    assert _names(results) == {"Card A", "Card C"}


def test_simple_free_text_still_works(fixture_db):
    # free text matches name/type/oracle broadly; "gets" only in Card B's oracle
    results = search_commander_legal_cards(query="gets")
    assert _names(results) == {"Card B"}


def test_type_filter_combines_with_structured(fixture_db):
    # --type creature + oracle terms; all are creatures so type filter is a no-op here
    results = search_commander_legal_cards(
        query='oracle:"can\'t be blocked" oracle:target',
        type_filter="creature",
    )
    assert _names(results) == {"Card A"}
    # --type artifact excludes everything
    results = search_commander_legal_cards(
        query="oracle:creature", type_filter="artifact"
    )
    assert _names(results) == set()


def test_mana_value_with_oracle(fixture_db):
    # mv<=3 excludes Card C (mv 5)
    results = search_commander_legal_cards(query="mv<=3 oracle:creature")
    assert _names(results) == {"Card A", "Card B"}


def test_conflicting_mana_filters_raise(fixture_db):
    from mtgcli.cards.query_parser import QueryConflictError
    with pytest.raises(QueryConflictError):
        search_commander_legal_cards(query="mv<=2 mv>=5")


# --- repeatable CLI filter options (extra_filters) ---

from mtgcli.cards.query_parser import empty_parsed


def _filters(**kw):
    f = empty_parsed()
    f.update(kw)
    return f


def test_extra_oracle_terms_and(fixture_db):
    results = search_commander_legal_cards(
        extra_filters=_filters(oracle_terms=["can't be blocked", "target", "creature"])
    )
    assert _names(results) == {"Card A"}


def test_extra_single_oracle_term_includes_more(fixture_db):
    results = search_commander_legal_cards(extra_filters=_filters(oracle_terms=["target"]))
    assert _names(results) == {"Card A", "Card B"}


def test_extra_name_filter(fixture_db):
    results = search_commander_legal_cards(extra_filters=_filters(name_terms=["card b"]))
    assert _names(results) == {"Card B"}


def test_extra_card_type_filter_and(fixture_db):
    results = search_commander_legal_cards(extra_filters=_filters(type_terms=["creature", "human"]))
    assert _names(results) == {"Card A", "Card B", "Card C"}
    results = search_commander_legal_cards(extra_filters=_filters(type_terms=["artifact"]))
    assert _names(results) == set()


def test_extra_mv_lte_gte(fixture_db):
    results = search_commander_legal_cards(extra_filters=_filters(mana_value_lte=3.0))
    assert _names(results) == {"Card A", "Card B"}
    results = search_commander_legal_cards(extra_filters=_filters(mana_value_gte=5.0))
    assert _names(results) == {"Card C"}


def test_query_string_and_extra_filters_combine(fixture_db):
    # query: oracle:target ; extra: oracle "can't be blocked" → only Card A
    results = search_commander_legal_cards(
        query="oracle:target",
        extra_filters=_filters(oracle_terms=["can't be blocked"]),
    )
    assert _names(results) == {"Card A"}


# --- CLI level ---

from typer.testing import CliRunner
import json as _json
from mtgcli.cli import app

_runner = CliRunner()


def _cli_names(*args):
    result = _runner.invoke(app, ["search", *args, "--json-output"])
    assert result.exit_code == 0, result.output
    return {c["name"] for c in _json.loads(result.output)}


def test_cli_repeatable_oracle_and(fixture_db):
    names = _cli_names("--oracle", "can't be blocked", "--oracle", "target", "--oracle", "creature")
    assert names == {"Card A"}


def test_cli_text_alias_for_oracle(fixture_db):
    names = _cli_names("--text", "can't be blocked", "--text", "target", "--text", "creature")
    assert names == {"Card A"}


def test_cli_name_and_card_type(fixture_db):
    names = _cli_names("--name", "Card B", "--card-type", "creature")
    assert names == {"Card B"}


def test_cli_mv_lte(fixture_db):
    names = _cli_names("--mv-lte", "3")
    assert names == {"Card A", "Card B"}


def test_cli_query_string_combines_with_options(fixture_db):
    names = _cli_names("oracle:target", "--oracle", "can't be blocked")
    assert names == {"Card A"}


def test_cli_old_query_syntax_still_works(fixture_db):
    names = _cli_names('''oracle:"can't be blocked" oracle:target''')
    assert names == {"Card A"}


def test_cli_no_args_errors(fixture_db):
    result = _runner.invoke(app, ["search"])
    assert result.exit_code == 1
    assert "Provide a query string" in result.output
