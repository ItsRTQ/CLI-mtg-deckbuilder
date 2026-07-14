"""Regression: Consistency-engine Fase 1 ingest fields (2026-07-06).

New columns wired through normalize -> schema -> row -> INSERT (the count sync is
covered by the existing schema-sync test): keywords (Scryfall's parsed list),
loyalty (face-aware), produced_mana, all_parts (slimmed; PARKED for v0.9.0),
image_url (front-face normal; PARKED for v0.9.0). The DB itself is rebuilt
MANUALLY by the user — these tests run on fakes, no DB required.
"""
from mtgcli.data.build_sqlite import _to_row, _CREATE_TABLE, _INSERT_SQL
from mtgcli.data.normalize_cards import (
    get_all_parts, get_image_url, get_loyalty, normalize_card,
)


def _raw(**over):
    base = {
        "oracle_id": "x-1", "name": "Test Card", "mana_cost": "{1}", "cmc": 1.0,
        "type_line": "Creature", "oracle_text": "Flying", "power": "1", "toughness": "1",
        "colors": [], "color_identity": [], "legalities": {"commander": "legal"},
        "prices": {}, "layout": "normal", "games": ["paper"], "digital": False,
        "finishes": ["nonfoil"],
    }
    base.update(over)
    return base


def test_keywords_ingested_and_default_empty():
    n = normalize_card(_raw(keywords=["Flying", "Storm"]))
    assert n["keywords"] == ["Flying", "Storm"]
    assert normalize_card(_raw())["keywords"] == []


def test_loyalty_top_level_and_face_fallback():
    assert normalize_card(_raw(loyalty="4"))["loyalty"] == "4"
    dfc = _raw(card_faces=[{"name": "Front"}, {"name": "Back", "loyalty": "3"}])
    assert get_loyalty(dfc) == "3"
    assert get_loyalty(_raw()) is None


def test_produced_mana_none_when_absent():
    assert normalize_card(_raw(produced_mana=["R", "W"]))["produced_mana"] == ["R", "W"]
    assert normalize_card(_raw())["produced_mana"] is None


def test_all_parts_slimmed():
    parts = [{"object": "related_card", "id": "abc", "component": "token",
              "name": "Food", "type_line": "Token Artifact — Food",
              "uri": "https://api/..."}]
    out = get_all_parts(_raw(all_parts=parts))
    assert out == [{"component": "token", "name": "Food",
                    "type_line": "Token Artifact — Food", "id": "abc"}]
    assert "uri" not in out[0] and "object" not in out[0]
    assert get_all_parts(_raw()) is None


def test_image_url_top_and_face_fallback():
    assert get_image_url(_raw(image_uris={"normal": "https://img/n.jpg"})) == "https://img/n.jpg"
    dfc = _raw(card_faces=[{"image_uris": {"normal": "https://img/front.jpg"}}])
    assert get_image_url(dfc) == "https://img/front.jpg"
    assert get_image_url(_raw()) is None


def test_row_carries_new_fields_and_counts_align():
    n = normalize_card(_raw(keywords=["Flying"], loyalty="4",
                            produced_mana=["G"], image_uris={"normal": "u"}))
    row = _to_row(n)
    schema_cols = [l.strip().split()[0] for l in _CREATE_TABLE.splitlines()
                   if l.strip() and not l.strip().startswith(("CREATE", ");"))]
    placeholders = _INSERT_SQL.split("VALUES")[1].count("?")
    assert len(row) == len(schema_cols) == placeholders
    # spot the values landed (json-encoded where applicable)
    assert '"Flying"' in row[schema_cols.index("keywords")]
    assert row[schema_cols.index("loyalty")] == "4"
    assert row[schema_cols.index("image_url")] == "u"


def test_rarity_ingested_per_kept_printing():
    # rarity is per-printing — normalized straight from the raw field, None-safe
    n = normalize_card(_raw(rarity="mythic"))
    assert n["rarity"] == "mythic"
    assert normalize_card(_raw())["rarity"] is None
    row = _to_row(n)
    schema_cols = [l.strip().split()[0] for l in _CREATE_TABLE.splitlines()
                   if l.strip() and not l.strip().startswith(("CREATE", ");"))]
    assert row[schema_cols.index("rarity")] == "mythic"
