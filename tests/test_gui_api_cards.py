"""Regression: gui_api card endpoints (v0.9.0 Task 6)."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mtgcli.config import SQLITE_PATH
from mtgcli.gui_api.app import create_app
from mtgcli.gui_api.deps import get_repo

needs_db = pytest.mark.skipif(
    not Path(str(SQLITE_PATH)).exists(), reason="card DB not built"
)


class _FakeRepo:
    def __init__(self, cards=None):
        self.cards = cards or {}

    def get_card_by_exact_name(self, name):
        return self.cards.get(name.lower())

    def suggest_similar_names(self, name, limit=5):
        return [{"name": "Sol Ring"}, {"name": "Sol Talisman"}][:limit]


def _client(repo=None):
    app = create_app()
    if repo is not None:
        app.dependency_overrides[get_repo] = lambda: repo
    return TestClient(app)


def test_card_by_name_found_and_404_with_suggestions():
    repo = _FakeRepo({"sol ring": {"name": "Sol Ring", "mana_value": 1.0,
                                   "type_line": "Artifact", "usd_price": 1.06}})
    c = _client(repo)
    ok = c.get("/api/cards/Sol Ring")
    assert ok.status_code == 200 and ok.json()["name"] == "Sol Ring"
    nf = c.get("/api/cards/Sol Rign")
    assert nf.status_code == 404
    err = nf.json()["detail"]["error"]
    assert err["type"] == "validation" and "Sol Ring" in err["suggestions"]


def test_search_requires_some_filter():
    r = _client(_FakeRepo()).get("/api/cards/search")
    assert r.status_code == 422


def test_search_params_passthrough_and_limit_cap(monkeypatch):
    import mtgcli.gui_api.routers.cards as cards_mod
    seen = {}

    def fake_search(query=None, colors=None, limit=50, type_filter=None,
                    extra_filters=None, rarity=None):
        seen.update(query=query, colors=colors, limit=limit,
                    type_filter=type_filter, extra=extra_filters)
        return [{"name": "Kiki-Jiki, Mirror Breaker"}]

    monkeypatch.setattr(cards_mod, "search_commander_legal_cards", fake_search)
    c = _client(_FakeRepo())
    r = c.get("/api/cards/search", params={"q": "type:legendary kiki", "colors": "R",
                                           "type": "creature", "limit": 30,
                                           "oracle": "haste", "mv_lte": 5})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 1 and body["results"][0]["name"].startswith("Kiki")
    assert seen["query"] == "type:legendary kiki" and seen["colors"] == "R"
    assert seen["type_filter"] == "creature"
    assert seen["limit"] == 31                      # chunk = offset + limit + 1
    assert seen["extra"]["oracle_terms"] == ["haste"]
    assert seen["extra"]["mana_value_lte"] == 5
    # repeatable oracle: fragments AND together (the GUI's "+" chips)
    r2 = c.get("/api/cards/search",
               params=[("q", "kiki"), ("oracle", "human"), ("oracle", "draw"),
                       ("oracle", "  ")])
    assert r2.status_code == 200
    assert seen["extra"]["oracle_terms"] == ["human", "draw"]   # blanks dropped
    # limit is capped by validation, not clamped silently
    assert c.get("/api/cards/search", params={"q": "x", "limit": 500}).status_code == 422


def _many(n):
    return [{"name": f"Card {i:03d}", "usd_price": float(i)} for i in range(n)]


def test_search_pagination_slices_and_has_more(monkeypatch):
    import mtgcli.gui_api.routers.cards as cards_mod
    monkeypatch.setattr(cards_mod, "search_commander_legal_cards",
                        lambda **k: _many(min(k["limit"], 100)))
    c = _client(_FakeRepo())
    p0 = c.get("/api/cards/search", params={"q": "x", "limit": 18, "offset": 0}).json()
    assert p0["count"] == 18 and p0["has_more"] is True
    assert p0["results"][0]["name"] == "Card 000"
    p1 = c.get("/api/cards/search", params={"q": "x", "limit": 18, "offset": 18}).json()
    assert p1["offset"] == 18 and p1["results"][0]["name"] == "Card 018"
    # a short final page: source returns exactly what fits -> no more
    monkeypatch.setattr(cards_mod, "search_commander_legal_cards",
                        lambda **k: _many(20))
    last = c.get("/api/cards/search", params={"q": "x", "limit": 18, "offset": 18}).json()
    assert last["count"] == 2 and last["has_more"] is False


def test_search_commanders_only_uses_exact_flag(monkeypatch):
    import mtgcli.gui_api.routers.cards as cards_mod
    cardset = [
        {"name": "Krenko, Mob Boss", "can_be_commander": True},
        {"name": "Krenko's Buzzcrusher", "can_be_commander": False},
        {"name": "Shorikai, Genesis Engine", "can_be_commander": True},  # vehicle override
    ]
    monkeypatch.setattr(cards_mod, "search_commander_legal_cards",
                        lambda **k: cardset)
    c = _client(_FakeRepo())
    body = c.get("/api/cards/search",
                 params={"name": "krenko", "commanders_only": True}).json()
    names = [r["name"] for r in body["results"]]
    assert names == ["Krenko, Mob Boss", "Shorikai, Genesis Engine"]


def test_search_rarity_passes_to_sql_layer(monkeypatch):
    # rarity filters at the SQL level (a scarce rarity must not starve the page
    # the way a post-filter chunk could)
    import mtgcli.gui_api.routers.cards as cards_mod
    seen = {}

    def fake_search(**k):
        seen.update(k)
        return [{"name": "Big Mythic", "rarity": "mythic"}]

    monkeypatch.setattr(cards_mod, "search_commander_legal_cards", fake_search)
    c = _client(_FakeRepo())
    body = c.get("/api/cards/search",
                 params={"name": "x", "rarity": "Mythic"}).json()
    assert seen["rarity"] == "Mythic"
    assert [r["name"] for r in body["results"]] == ["Big Mythic"]


def test_search_max_price_filters_and_keeps_unpriced(monkeypatch):
    import mtgcli.gui_api.routers.cards as cards_mod
    cardset = [{"name": "Cheap", "usd_price": 1.0},
               {"name": "Pricey", "usd_price": 40.0},
               {"name": "Unknown", "usd_price": None}]
    monkeypatch.setattr(cards_mod, "search_commander_legal_cards",
                        lambda **k: cardset)
    c = _client(_FakeRepo())
    body = c.get("/api/cards/search", params={"q": "x", "max_price": 5}).json()
    names = [r["name"] for r in body["results"]]
    assert names == ["Cheap", "Unknown"]           # unpriced kept, pricey dropped


def test_search_bad_type_is_422_with_contract(monkeypatch):
    c = _client(_FakeRepo())
    r = c.get("/api/cards/search", params={"q": "draw", "type": "notatype"})
    assert r.status_code == 422
    assert r.json()["detail"]["error"]["type"] == "usage"


@needs_db
def test_search_integration_against_real_db():
    r = _client().get("/api/cards/search",
                      params={"q": "type:legendary kiki-jiki", "type": "creature"})
    assert r.status_code == 200
    names = [c["name"] for c in r.json()["results"]]
    assert any("Kiki-Jiki" in n for n in names)
