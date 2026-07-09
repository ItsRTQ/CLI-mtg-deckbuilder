"""Regression: the qualifier-interruption GENERAL mechanism (utils/phrase_match.py).

Tag phrases may carry the ``" * "`` wildcard: literal parts in order with a bounded
same-clause gap (<= QUALIFIER_GAP chars, never crossing '.', ';' or a newline).
Plain phrases behave exactly like the old substring check, so the mechanism ships
with zero behavior change until a wildcard phrase enters the vocabulary.

Founding sightings covered: Mirko #21 ("with power less than Mirko's"), Athreos #28
("you own"), Angelic Accord (full build #3, "4 or more" — first production case).
"""
from mtgcli.utils.phrase_match import (
    QUALIFIER_GAP, any_phrase_matches, phrase_matches, phrase_to_like,
)


# ---------- plain phrases: byte-for-byte the old behavior ----------

def test_plain_phrase_is_substring():
    assert phrase_matches("another creature dies", "whenever another creature dies, draw")
    assert not phrase_matches("another creature dies", "whenever a creature dies")


def test_empty_text():
    assert not phrase_matches("x", "")
    assert not phrase_matches("x", None)


# ---------- wildcard semantics ----------

def test_wildcard_matches_zero_gap_form():
    # the plain form still matches (gap swallows the single space)
    assert phrase_matches("another creature * dies", "whenever another creature dies, draw")


def test_wildcard_matches_qualifier_forms():
    # Athreos (#28)
    assert phrase_matches("another creature * dies", "whenever another creature you own dies")
    # Angelic Accord (production sighting, full build #3)
    assert phrase_matches("you gained * life this turn", "if you gained 4 or more life this turn")
    # Mirko (#21, the founding member)
    assert phrase_matches(
        "creature card * from your graveyard to the battlefield",
        "return target creature card with power less than mirko's from your graveyard to the battlefield",
    )


def test_wildcard_gap_is_bounded():
    filler = "x" * (QUALIFIER_GAP + 10)
    assert not phrase_matches("another creature * dies", f"another creature {filler} dies")


def test_wildcard_gap_never_crosses_clause():
    # a period between the parts = different clauses, must NOT match
    assert not phrase_matches("another creature * dies", "another creature you control. When it dies")
    assert not phrase_matches("another creature * dies", "another creature\nwhen it dies")


def test_any_phrase_matches():
    assert any_phrase_matches(["nope", "you gained * life this turn"],
                              "if you gained 3 or more life this turn")
    assert not any_phrase_matches(["nope"], "some text")


# ---------- SQL retrieval side ----------

def test_phrase_to_like_plain():
    assert phrase_to_like("another creature dies") == "%another creature dies%"


def test_phrase_to_like_wildcard():
    assert phrase_to_like("another creature * dies") == "%another creature%dies%"
