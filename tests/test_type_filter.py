import pytest

from mtgcli.cards.search import (
    search_commander_legal_cards,
    search_by_tags,
    normalize_type_filter,
    card_matches_type,
    UnknownTypeFilterError,
)


# --- normalize_type_filter ---

def test_normalize_basic():
    assert normalize_type_filter("creature") == "creature"
    assert normalize_type_filter("ARTIFACT") == "artifact"


def test_normalize_plural_aliases():
    assert normalize_type_filter("creatures") == "creature"
    assert normalize_type_filter("sorceries") == "sorcery"
    assert normalize_type_filter("lands") == "land"


def test_normalize_compound_aliases():
    assert normalize_type_filter("spell") == "spell"
    assert normalize_type_filter("permanent") == "permanent"
    assert normalize_type_filter("nonland") == "nonland"


def test_normalize_invalid_raises():
    with pytest.raises(UnknownTypeFilterError):
        normalize_type_filter("banana")


# --- card_matches_type ---

def test_card_matches_type_basic():
    card = {"type_line": "Legendary Artifact Creature — Golem"}
    assert card_matches_type(card, "artifact")
    assert card_matches_type(card, "creature")
    assert not card_matches_type(card, "instant")


def test_card_matches_type_nonland():
    assert card_matches_type({"type_line": "Instant"}, "nonland")
    assert not card_matches_type({"type_line": "Basic Land — Forest"}, "nonland")


# --- search integration (requires DB) ---

def test_search_type_creature_only_creatures():
    results = search_commander_legal_cards(query="draw", limit=30, type_filter="creature")
    assert results, "expected some creature results for 'draw'"
    for c in results:
        assert "creature" in c["type_line"].lower()


def test_search_type_artifact_only_artifacts():
    results = search_commander_legal_cards(query="Add", limit=30, type_filter="artifact")
    assert results
    for c in results:
        assert "artifact" in c["type_line"].lower()


def test_search_type_case_insensitive():
    lower = search_commander_legal_cards(query="draw", limit=20, type_filter="creature")
    upper = search_commander_legal_cards(query="draw", limit=20, type_filter="CREATURE")
    assert [c["name"] for c in lower] == [c["name"] for c in upper]


def test_search_type_plural_normalizes():
    singular = search_commander_legal_cards(query="draw", limit=20, type_filter="creature")
    plural = search_commander_legal_cards(query="draw", limit=20, type_filter="creatures")
    assert [c["name"] for c in singular] == [c["name"] for c in plural]


def test_search_type_combines_with_type_token():
    # type:vampire (subtype) AND --type creature
    results = search_commander_legal_cards(query="type:vampire", limit=30, type_filter="creature")
    for c in results:
        tl = c["type_line"].lower()
        assert "vampire" in tl and "creature" in tl


def test_search_type_artifact_matches_artifact_creature():
    results = search_commander_legal_cards(query="", limit=200, type_filter="artifact")
    # at least one result should be an Artifact Creature
    assert any("creature" in c["type_line"].lower() for c in results)


def test_search_tags_type_filter():
    results = search_by_tags(tags=["card_draw"], limit=30, type_filter="creature")
    for c in results:
        assert "creature" in c["type_line"].lower()


# --- CLI-level suggest integration ---

from typer.testing import CliRunner
import json as _json
from mtgcli.cli import app

_runner = CliRunner()


def _suggest_json(*args):
    result = _runner.invoke(app, ["suggest", *args, "--json-output"])
    assert result.exit_code == 0, result.output
    return _json.loads(result.output)


def test_suggest_type_creature_only_creatures():
    cards = _suggest_json("--commander", "Edgar Markov", "--role", "card_draw",
                          "--type", "creature", "--limit", "10")
    for c in cards:
        assert "creature" in c["type_line"].lower()


def test_suggest_type_artifact_ramp_matches_both():
    cards = _suggest_json("--commander", "Brago, King Eternal", "--role", "ramp",
                          "--type", "artifact", "--limit", "10")
    for c in cards:
        assert "artifact" in c["type_line"].lower()
        # role still enforced: ramp candidates carry matched_tags
        assert c.get("suggestion_score", 0) > 0


def test_suggest_type_land_does_not_surface_plain_lands_as_ramp():
    cards = _suggest_json("--commander", "Brago, King Eternal", "--role", "ramp",
                          "--type", "land", "--limit", "20")
    # Any land returned must have qualified as ramp (non-zero score), not just be a land
    for c in cards:
        assert c.get("suggestion_score", 0) > 0


def test_suggest_invalid_type_errors():
    result = _runner.invoke(app, ["suggest", "--commander", "Edgar Markov",
                                  "--role", "ramp", "--type", "banana"])
    assert result.exit_code == 1
    assert "Unknown type filter" in result.output


@pytest.mark.parametrize("args", [
    ["search", "--type", "Rogue", "--json-output"],
    ["search-tags", "evasion", "--type", "Rogue", "--json-output"],
    ["suggest", "--commander", "Edgar Markov", "--role", "ramp", "--type", "Rogue", "--json-output"],
])
def test_invalid_type_json_is_validation_error_not_crash(args):
    """Regression (cli.py split): the --type validation path calls _emit_json_error inside
    the command; after the split it was undefined in commands/search.py, so the crash
    boundary masked it as {"type": "internal", "exception": "NameError"}. The generic
    boundary test only checked for an "error" key, so it passed on the crash. Pin the
    REAL contract: a clean validation error that suggests --subtype."""
    result = _runner.invoke(app, args)
    assert result.exception is None or isinstance(result.exception, SystemExit), result.exception
    err = _json.loads(result.output)["error"]
    assert err["type"] == "validation"
    assert "NameError" not in str(err)
    assert "subtype" in err["message"]


@pytest.mark.parametrize("args,fragment", [
    (["search", "--json-output"], "query string"),
    (["search-tags", "--json-output"], "at least one tag"),
    (["suggest", "--commander", "Edgar Markov", "--role", "synergy", "--json-output"],
     "not a valid role"),
])
def test_local_validation_respects_json_output(args, fragment):
    """The search family's LOCAL validation errors (no query/filters, no tags,
    --role synergy) used to print plain rich text under --json-output, breaking
    agent parsers. They must emit the structured validation error instead."""
    result = _runner.invoke(app, args)
    err = _json.loads(result.output)["error"]
    assert err["type"] == "validation"
    assert fragment in err["message"]
