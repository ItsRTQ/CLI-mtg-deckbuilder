"""Regression: the DECK build-context object (Consistency-engine Fase 2).

Composition (not a List subclass); mutation only via add()/remove() — batch-friendly
and ATOMIC — enforcing size (quantity-aware, commanders excluded), singleton (basics
merge instead) and color identity. Combos grouped by class at deck level. Metrics per
the user spec: total_by_purpose, total_price, mana_curve (+ the user's TVD-based
score formula), size, card_types (Moxfield-style primary type). Serialization
persists judgment only.
"""
import pytest

from mtgcli.models import Card, Deck, DeckError, IDEAL_CURVE


def _row(name, ident='["R","W"]', type_line="Artifact", mv=2.0, price=1.0, **over):
    base = {
        "name": name, "mana_cost": "{2}", "mana_value": mv, "type_line": type_line,
        "oracle_text": "text", "power": None, "toughness": None, "loyalty": None,
        "colors": ident, "color_identity": ident, "keywords": "[]",
        "produced_mana": None, "all_parts": None, "image_url": None,
        "edhrec_rank": 100, "usd_price": price, "game_changer": 0,
    }
    base.update(over)
    return base


def _card(name, purpose=("FLEX",), ident='[]', qty=1, **over):
    return Card(name, list(purpose), quantity=qty, db_row=_row(name, ident=ident, **over))


def _commander():
    return Card("Ragost", ["WINCON"], db_row=_row("Ragost", ident='["R","W"]',
                                                  type_line="Legendary Creature — Lobster"))


# ---------- init ----------

def test_commanders_one_or_two_only():
    Deck(_commander())
    Deck([_commander(), Card("Partner", ["FLEX"], db_row=_row("Partner", ident='["W"]'))])
    with pytest.raises(DeckError):
        Deck([])


def test_max_size_shrinks_with_partner():
    solo = Deck(_commander())
    duo = Deck([_commander(), Card("P", ["FLEX"], db_row=_row("P", ident='["R"]'))])
    assert solo.max_size == 99 and duo.max_size == 98


# ---------- guardians (atomic batches) ----------

def test_add_batch_atomic_on_singleton():
    d = Deck(_commander())
    d.add(_card("Sol Ring"))
    with pytest.raises(DeckError) as e:
        d.add([_card("Fellwar Stone"), _card("Sol Ring")])
    assert "singleton" in str(e.value)
    assert d.size() == 1  # nothing from the batch entered


def test_add_rejects_in_batch_duplicates_and_nonbasic_quantity():
    d = Deck(_commander())
    with pytest.raises(DeckError):
        d.add([_card("Twin"), _card("Twin")])
    with pytest.raises(DeckError) as e:
        d.add(_card("Nonbasic", qty=3))
    assert "quantity" in str(e.value)


def test_add_rejects_color_identity_violation():
    d = Deck(_commander())  # RW
    with pytest.raises(DeckError) as e:
        d.add(_card("Blue Thing", ident='["U"]'))
    assert "color identity" in str(e.value)


def test_add_rejects_size_overflow_quantity_aware():
    d = Deck(_commander())
    d.add(_card("Mountain", ident='[]', qty=98, type_line="Basic Land — Mountain"))
    with pytest.raises(DeckError) as e:
        d.add(_card("Plains", ident='[]', qty=2, type_line="Basic Land — Plains"))
    assert "99" in str(e.value)


def test_basics_merge_instead_of_singleton():
    d = Deck(_commander())
    d.add(_card("Mountain", ident='[]', qty=5, type_line="Basic Land — Mountain"))
    d.add(_card("Mountain", ident='[]', qty=3, type_line="Basic Land — Mountain"))
    assert d.size() == 8
    assert len(d.cards) == 1 and d.cards[0].quantity == 8


def test_remove_batch_atomic_and_basics_decrement():
    d = Deck(_commander())
    d.add([_card("A"), _card("Mountain", ident='[]', qty=5, type_line="Basic Land — Mountain")])
    with pytest.raises(DeckError):
        d.remove(["A", "Ghost"])  # atomic: A survives
    assert d.size() == 6
    d.remove("Mountain", quantity=2)
    assert d.size() == 4  # 3 mountains + A... wait: A=1 + Mountain 3 = 4 ✓
    d.remove("A")
    assert d.size() == 3


# ---------- combos ----------

def test_add_combo_classes_and_aliases():
    d = Deck(_commander())
    d.add_combo("autowin", ["X", "Y"], "does the thing")
    d.add_combo("non-infinite", ["X", "Z"])
    assert len(d.combos["auto_win"]) == 1
    assert d.combos["auto_win"][0]["how_to"] == "does the thing"
    assert len(d.combos["non_infinite"]) == 1
    with pytest.raises(DeckError):
        d.add_combo("mega", ["X"])
    with pytest.raises(DeckError):
        d.add_combo("infinite", [])


# ---------- metrics ----------

def test_total_by_purpose_and_price_quantity_aware():
    d = Deck(_commander())
    d.add([_card("A", ("RAMP", "SYNERGY"), price=2.5),
           _card("Mountain", ("FLEX",), ident='[]', qty=4,
                 type_line="Basic Land — Mountain", price=0.1)])
    assert d.total_by_purpose() == {"FLEX": 4, "RAMP": 1, "SYNERGY": 1}
    assert d.total_price() == round(2.5 + 0.4, 2)


def test_total_price_by_type_primary_quantity_aware():
    d = Deck(_commander())
    d.add([_card("AC", type_line="Artifact Creature — Golem", price=3.0),
           _card("Rock", type_line="Artifact", price=1.25),
           _card("Mountain", ("FLEX",), ident='[]', qty=4,
                 type_line="Basic Land — Mountain", price=0.1),
           _card("Mystery", type_line="Instant", price=None)])
    by_type = d.total_price_by_type()
    # Artifact Creature buckets as creature (primary type); 4x quantity-aware
    # lands; unknown price sums as $0 (same convention as total_price)
    assert by_type == {"creature": 3.0, "artifact": 1.25, "land": 0.4, "instant": 0.0}
    assert list(by_type) == ["creature", "artifact", "land", "instant"]  # cost desc
    assert round(sum(by_type.values()), 2) == d.total_price()


def test_card_types_moxfield_primary():
    d = Deck(_commander())
    d.add([_card("AC", type_line="Artifact Creature — Golem"),
           _card("Saga", type_line="Enchantment — Saga"),
           _card("Dryad", type_line="Land Creature — Forest Dryad", ident='[]')])
    counts = d.card_type_counts()
    assert counts == {"creature": 1, "enchantment": 1, "land": 1}  # primary only
    assert "creatures=1" in d.card_types()


def test_mana_curve_and_user_score_formula():
    d = Deck(_commander())
    d.add([_card("One", mv=1.0), _card("Two", mv=2.0), _card("Big", mv=9.0),
           _card("Mountain", ident='[]', qty=10, type_line="Basic Land — Mountain")])
    curve = d.mana_curve()
    assert curve["1"] == 1 and curve["2"] == 1 and curve["7+"] == 1
    assert sum(curve.values()) == 3  # lands excluded
    # hand-computed: shares 1/3 in buckets 1,2,7+; TVD vs IDEAL_CURVE
    tvd = sum(abs((1/3 if b in ("1", "2", "7+") else 0.0) - IDEAL_CURVE[b])
              for b in IDEAL_CURVE) / 2
    assert d.mana_curve_score() == round(10 * max(0.0, 1 - tvd), 2)
    assert Deck(_commander()).mana_curve_score() is None  # empty deck: None, not fake 10


# ---------- print + serialization ----------

def test_str_count_plus_moxfield_format():
    d = Deck(_commander())
    d.add(_card("Sol Ring"))
    s = str(d)
    assert s.startswith("1 cards") or s.startswith("1 card")
    assert "Commander\n1 Ragost" in s
    assert "Deck\n" in s and "1 Sol Ring" in s


class _FakeRepo:
    def get_card_by_exact_name(self, name):
        basics = {"Mountain": "Basic Land — Mountain"}
        return _row(name, ident='["R","W"]' if name != "Mountain" else '[]',
                    type_line=basics.get(name, "Artifact"))

    def suggest_similar_names(self, name):
        return []


def test_save_load_roundtrip_judgment_only(tmp_path):
    d = Deck(_commander(), agent_note="food cannon")
    d.add([_card("Sol Ring", ("RAMP", "SYNERGY")),
           _card("Mountain", ("FLEX",), ident='[]', qty=3, type_line="Basic Land — Mountain")])
    d.add_combo("infinite", ["X", "Y"], "loop")
    p = tmp_path / "deck.json"
    d.save(p)
    raw = p.read_text()
    assert "oracle_text" not in raw and "usd_price" not in raw  # facts never persisted
    d2 = Deck.load(p, repo=_FakeRepo())
    assert d2.size() == d.size()
    assert d2.total_by_purpose() == d.total_by_purpose()
    assert d2.combos == d.combos
    assert d2.agent_note == "food cannon"
