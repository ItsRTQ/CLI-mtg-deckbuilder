"""Regression: /api/bulk + /api/decks (the Collection page's backend)."""
from fastapi.testclient import TestClient

import mtgcli.core.gui_settings as gs_mod
import mtgcli.deckbuilder.user_bulk as ub
from mtgcli.gui_api.app import create_app
from mtgcli.gui_api.deps import get_repo, get_repo_optional


class _FakeRepo:
    PRICES = {"rhystic study": 35.0, "smothering tithe": 20.0}
    TYPES = {"sol ring": "Artifact", "mountain": "Basic Land — Mountain",
             "krenko, mob boss": "Legendary Creature — Goblin Warrior",
             "jaya ballard": "Legendary Planeswalker — Jaya"}
    COLORS = {"rhystic study": ["U"], "smothering tithe": ["W"],
              "krenko, mob boss": ["R"], "goblin warchief": ["R"],
              "jaya ballard": ["R"]}
    KNOWN = {"rhystic study", "smothering tithe", "sol ring", "mountain",
             "krenko, mob boss", "some unknown card", "goblin warchief",
             "jaya ballard"}

    def get_card_by_exact_name(self, name):
        low = name.lower()
        if low not in self.KNOWN:
            return None
        return {"name": name.title() if low != "krenko, mob boss" else "Krenko, Mob Boss",
                "usd_price": self.PRICES.get(low),
                "type_line": self.TYPES.get(low),
                "color_identity": self.COLORS.get(low, []),
                "image_url": f"https://img.test/normal/{low}.jpg",
                "mana_value": 1.0,
                "can_be_commander": low == "krenko, mob boss"}

    def suggest_similar_names(self, name, limit=5):
        return []


def _client(monkeypatch, tmp_path, bulk_lines=None, decks=None):
    monkeypatch.setattr(gs_mod, "GUI_SETTINGS_PATH", tmp_path / "gui_settings.json")
    bulk_dir = tmp_path / "bulk"
    bulk_dir.mkdir()
    if bulk_lines is not None:
        (bulk_dir / "collection.txt").write_text("\n".join(bulk_lines) + "\n")
    monkeypatch.setattr(ub, "_configured_bulk_dir", lambda: bulk_dir)

    lib = tmp_path / "library"
    for name, files in (decks or {}).items():
        d = lib / name
        d.mkdir(parents=True)
        for fname, content in files.items():
            (d / fname).write_text(content)
    gs_mod.save_gui_settings({"builds_save_dir": str(lib)})

    app = create_app()
    app.dependency_overrides[get_repo] = lambda: _FakeRepo()
    app.dependency_overrides[get_repo_optional] = lambda: _FakeRepo()
    return TestClient(app)


def test_bulk_endpoint_lists_owned_with_value(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path,
                bulk_lines=["Rhystic Study", "Smothering Tithe", "Some Unknown Card"])
    r = c.get("/api/bulk")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 3
    assert body["known_value"] == 55.0
    assert body["unknown_count"] == 1
    assert "Sol Ring" in body["always_free"]
    assert body["source"].endswith("collection.txt")


def test_bulk_endpoint_empty_collection(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)  # no collection.txt at all
    body = c.get("/api/bulk").json()
    assert body["count"] == 0 and body["cards"] == []


def test_bulk_add_endpoint_adds_and_is_idempotent(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, bulk_lines=["Rhystic Study"])
    r = c.post("/api/bulk/add", json={"name": "smothering tithe"})
    assert r.status_code == 200
    body = r.json()
    # canonical DB name wins over the typed-in casing
    assert body["name"] == "Smothering Tithe" and body["added"] is True
    assert body["count"] == 2
    # the collection file actually gained the card (both forms written)
    bulk_txt = (tmp_path / "bulk" / "collection.txt").read_text()
    assert "Smothering Tithe" in bulk_txt and "Rhystic Study" in bulk_txt
    assert (tmp_path / "bulk" / "collection.json").exists()
    # idempotent: dropping it again doesn't duplicate
    again = c.post("/api/bulk/add", json={"name": "Smothering Tithe"}).json()
    assert again["added"] is False and again["count"] == 2


def test_bulk_import_adds_dedupes_and_skips(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, bulk_lines=["Rhystic Study"])
    r = c.post("/api/bulk/import", json={"text": (
        "1 Sol Ring\n"
        "4 smothering tithe\n"          # quantity ignored (ownership model)
        "Rhystic Study\n"               # already owned
        "1 Totally Fake Card\n"         # skipped, never invented
        "# a comment line\n"
        "Krenko, Mob Boss (SLD) 123 *F*\n")})  # Moxfield suffix stripped
    assert r.status_code == 200
    body = r.json()
    assert body["added"] == ["Sol Ring", "Smothering Tithe", "Krenko, Mob Boss"]
    assert body["already_owned"] == ["Rhystic Study"]
    assert body["skipped"] == ["Totally Fake Card"]
    assert body["count"] == 4
    bulk_txt = (tmp_path / "bulk" / "collection.txt").read_text()
    assert "Krenko, Mob Boss" in bulk_txt and "Rhystic Study" in bulk_txt
    assert "Totally Fake Card" not in bulk_txt


def test_bulk_import_empty_text_422(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)
    r = c.post("/api/bulk/import", json={"text": "  \n# only a comment\n"})
    assert r.status_code == 422
    assert r.json()["detail"]["error"]["type"] == "validation"
    # nothing written
    assert not (tmp_path / "bulk" / "collection.txt").exists()


def test_bulk_add_endpoint_unknown_card_404(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)

    class _NotFoundRepo(_FakeRepo):
        def get_card_by_exact_name(self, name):
            return None

        def suggest_similar_names(self, name, limit=5):
            return [{"name": "Sol Ring"}]

    from mtgcli.gui_api.deps import get_repo as _gr
    c.app.dependency_overrides[_gr] = lambda: _NotFoundRepo()
    r = c.post("/api/bulk/add", json={"name": "Sol Rign"})
    assert r.status_code == 404
    assert r.json()["detail"]["error"]["suggestions"] == ["Sol Ring"]


def test_decks_endpoint_lists_library(monkeypatch, tmp_path):
    import json
    c = _client(monkeypatch, tmp_path, decks={
        "Krenko-Mob-Boss-+B-Scrap-48usd": {
            "Krenko-Mob-Boss-+B-Scrap-48usd.txt": "1 Sol Ring\n32 Mountain\n",
            "Krenko-Mob-Boss-+B-Scrap-48usd.explanation.md": "# Deck",
            "deck_list.json": json.dumps({"commander": "Krenko, Mob Boss",
                                          "main_deck": []}),
        },
        "Old-Deck-100usd": {"Old-Deck-100usd.txt": "1 Sol Ring\n"},
        "Edgar-Markov-S-Mythic-3415usd": {},
    })
    body = c.get("/api/decks").json()
    assert len(body["decks"]) == 3
    by_name = {d["name"]: d for d in body["decks"]}
    krenko = by_name["Krenko-Mob-Boss-+B-Scrap-48usd"]
    assert krenko["card_count"] == 33 and krenko["has_explanation"] is True
    # banner metadata parsed from the folder-name convention + deck_list.json
    assert krenko["tier"] == "+B" and krenko["rank"] == "Scrap"
    assert krenko["cost_usd"] == 48
    assert krenko["commander"] == "Krenko, Mob Boss"
    edgar = by_name["Edgar-Markov-S-Mythic-3415usd"]
    assert edgar["tier"] == "S" and edgar["rank"] == "Mythic"
    assert edgar["cost_usd"] == 3415 and edgar["commander"] is None
    old = by_name["Old-Deck-100usd"]
    assert old["tier"] is None and old["rank"] is None and old["cost_usd"] == 100
    assert old["has_explanation"] is False


def test_deck_detail_and_traversal_guard(monkeypatch, tmp_path):
    import json
    c = _client(monkeypatch, tmp_path, decks={
        "MyDeck-1usd": {"MyDeck-1usd.txt": "1 Sol Ring\n",
                        "MyDeck-1usd.explanation.md": "# hola",
                        "deck_list.json": json.dumps({
                            "commander": "Krenko, Mob Boss",
                            "main_deck": [{"name": "Sol Ring", "quantity": 1},
                                          {"name": "Mountain", "quantity": 32}]})},
    })
    ok = c.get("/api/decks/MyDeck-1usd")
    assert ok.status_code == 200
    body = ok.json()
    assert "Sol Ring" in body["decklist"]
    assert body["explanation"].startswith("# hola")
    # sectioned, hydrated cards: commander first, then by primary type
    by_section = {}
    for card in body["cards"]:
        by_section.setdefault(card["section"], []).append(card)
    assert by_section["commander"][0]["name"] == "Krenko, Mob Boss"
    assert by_section["artifacts"][0]["name"] == "Sol Ring"
    assert by_section["lands"][0]["quantity"] == 32
    assert by_section["lands"][0]["image_url"].endswith("mountain.jpg")
    stats = body["stats"]
    assert stats["total_cards"] == 34          # commander + 1 + 32
    assert stats["section_counts"]["lands"] == 32
    assert c.get("/api/decks/nope").status_code == 404
    # traversal: the client/framework normalizes ..%2F away from the endpoint,
    # and unknown /api paths are JSON 404s (never the SPA's index.html);
    # dotted names are refused by the endpoint's own guard.
    assert c.get("/api/decks/..%2Fsecrets").status_code == 404
    assert c.get("/api/decks/.hidden").status_code == 404


def test_deck_import_endpoint(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)
    lib = tmp_path / "library"
    r = c.post("/api/decks/import", json={
        "commander": "krenko, mob boss",
        # Moxfield-style lines: set/collector suffix must strip; unknown skipped
        "decklist": "1 Krenko, Mob Boss\n1 Sol Ring (C21) 263\n"
                    "32 Mountain\n1 Not A Real Card\n",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["commander"] == "Krenko, Mob Boss"     # canonical casing
    assert body["imported"] == 2                        # Sol Ring + Mountain
    assert body["skipped"] == ["Not A Real Card"]
    build_dir = lib / body["build_name"]
    assert build_dir.is_dir()
    assert body["build_name"].startswith("Krenko")
    txt = (build_dir / f"{body['build_name']}.txt").read_text()
    assert "32 Mountain" in txt and "Sol Ring" in txt
    assert "Krenko" not in txt                          # commander -> command zone
    import json
    dl = json.loads((build_dir / "deck_list.json").read_text())
    assert dl["commander"] == "Krenko, Mob Boss"
    # bad commander -> 422 with the JSON contract
    bad = c.post("/api/decks/import", json={"commander": "Sol Ring",
                                            "decklist": "1 Mountain"})
    assert bad.status_code == 422


def test_deck_delete_endpoint(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, decks={
        "Doomed-1usd": {"Doomed-1usd.txt": "1 Sol Ring\n"},
        "Keeper-2usd": {"Keeper-2usd.txt": "1 Mountain\n"},
    })
    r = c.delete("/api/decks/Doomed-1usd")
    assert r.status_code == 200 and r.json()["deleted"] == "Doomed-1usd"
    assert not (tmp_path / "library" / "Doomed-1usd").exists()
    assert (tmp_path / "library" / "Keeper-2usd").exists()   # neighbors untouched
    names = [d["name"] for d in c.get("/api/decks").json()["decks"]]
    assert names == ["Keeper-2usd"]
    # unknown + traversal-shaped names -> 404
    assert c.delete("/api/decks/Doomed-1usd").status_code == 404
    assert c.delete("/api/decks/.hidden").status_code == 404


def test_explain_endpoint_runs_agent_and_copies_back(monkeypatch, tmp_path):
    import json
    import time as _time

    import mtgcli.core.build_workspace as bw_mod
    from mtgcli.core.providers import ProviderManager
    from mtgcli.core.providers.base import AgentProvider, ProviderInfo, ProviderResult

    deck_json = {"commander": "Krenko, Mob Boss",
                 "print_prefs": {"sol ring": {
                     "set": "LEA", "collector_number": "1",
                     "image_url": "https://img.test/normal/deck.jpg",
                     "rarity": "rare"}},
                 "main_deck": [{"name": "Sol Ring", "quantity": 1}]}
    c = _client(monkeypatch, tmp_path, decks={
        "Krenko-48usd": {"Krenko-48usd.txt": "1 Sol Ring\n",
                         "deck_list.json": json.dumps(deck_json)},
    })
    monkeypatch.setattr(bw_mod, "GUI_BUILDS_DIR", tmp_path / "gui-builds")

    class FakeExplainProvider(AgentProvider):
        name = "fake"
        supports_build = True

        def detect(self):
            return ProviderInfo(name="fake", installed=True, supports_build=True)

        def build(self, workspace, prompt_file, *, timeout, cancel_event=None):
            # the prompt must carry the owner's context answers
            prompt = prompt_file.read_text()
            assert "goblin swarm" in prompt and "Zealous Conscripts" in prompt
            (workspace / "output" / "explanation.md").write_text(
                "| Deck commander | TIER | RANK |\n# great deck")
            # the agent regenerates the deck WITHOUT print_prefs (not its contract)
            annotated = {k: v for k, v in deck_json.items() if k != "print_prefs"}
            annotated["main_deck"] = [
                {"name": "Sol Ring", "quantity": 1, "purpose": ["RAMP"]}]
            (workspace / "output" / "deck.json").write_text(json.dumps(annotated))
            return ProviderResult(ok=True, exit_code=0)

    c.app.state.provider_manager = ProviderManager([FakeExplainProvider()])
    r = c.post("/api/decks/Krenko-48usd/explain",
               json={"theme": "goblin swarm",
                     "combos": "Kiki-Jiki + Zealous Conscripts"})
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]
    deadline = _time.monotonic() + 10
    while _time.monotonic() < deadline:
        body = c.get(f"/api/builds/{job_id}").json()
        if body["status"] in ("succeeded", "failed", "timeout", "cancelled"):
            break
        _time.sleep(0.05)
    assert body["status"] == "succeeded", body
    # deliverables copied back — the folder may have been RENAMED to carry the
    # freshly computed tier/rank tokens (that's where the banner reads them)
    deck_name = body["result"]["deck_name"]
    lib_deck = tmp_path / "library" / deck_name
    assert lib_deck.is_dir()
    krenko_dirs = [d.name for d in (tmp_path / "library").iterdir()
                   if d.name.startswith("Krenko")]
    assert krenko_dirs == [deck_name]                     # old folder gone
    assert "great deck" in (lib_deck / f"{deck_name}.explanation.md").read_text()
    saved = json.loads((lib_deck / "deck_list.json").read_text())
    assert saved["main_deck"][0]["purpose"] == ["RAMP"]   # annotations landed
    # the user's print prefs were RE-INJECTED over the agent's rewrite
    assert saved["print_prefs"]["sol ring"]["set"] == "LEA"
    # deck without deck_list.json -> 422
    (tmp_path / "library" / "NoJson-1usd").mkdir()
    assert c.post("/api/decks/NoJson-1usd/explain", json={}).status_code == 422


def test_print_prefs_endpoints_and_application(monkeypatch, tmp_path):
    import json

    import mtgcli.core.print_prefs as pp_mod
    monkeypatch.setattr(pp_mod, "GUI_PRINTS_PATH", tmp_path / "gui_prints.json")

    deck_json = {"commander": "Krenko, Mob Boss",
                 "main_deck": [{"name": "Sol Ring", "quantity": 1}]}
    c = _client(monkeypatch, tmp_path,
                bulk_lines=["Sol Ring"],
                decks={"K-1usd": {"K-1usd.txt": "1 Sol Ring\n",
                                  "deck_list.json": json.dumps(deck_json)}})
    # default art comes from the DB
    assert c.get("/api/bulk").json()["cards"][0]["image_url"].endswith("sol ring.jpg")
    # choose another printing -> persisted
    r = c.put("/api/prints/Sol Ring", json={
        "set": "C21", "collector_number": "263",
        "image_url": "https://img.test/normal/solring-c21.jpg"})
    assert r.status_code == 200
    # ...and APPLIED on bulk and deck-detail hydration (case-insensitive by name)
    assert c.get("/api/bulk").json()["cards"][0]["image_url"].endswith("solring-c21.jpg")
    detail = c.get("/api/decks/K-1usd").json()
    ring = next(x for x in detail["cards"] if x["name"] == "Sol Ring")
    assert ring["image_url"].endswith("solring-c21.jpg")
    # clearing goes back to the DB default
    assert c.delete("/api/prints/sol ring").json()["cleared"] is True
    assert c.get("/api/bulk").json()["cards"][0]["image_url"].endswith("sol ring.jpg")
    # missing image_url -> 422
    assert c.put("/api/prints/Sol Ring", json={"image_url": ""}).status_code == 422


def test_deck_print_prefs_resolution_and_fallback(monkeypatch, tmp_path):
    import json

    import mtgcli.core.print_prefs as pp_mod
    monkeypatch.setattr(pp_mod, "GUI_PRINTS_PATH", tmp_path / "gui_prints.json")

    deck_json = {"commander": "Krenko, Mob Boss",
                 "main_deck": [{"name": "Sol Ring", "quantity": 1}]}
    c = _client(monkeypatch, tmp_path,
                bulk_lines=["Sol Ring"],
                decks={"K-1usd": {"K-1usd.txt": "1 Sol Ring\n",
                                  "deck_list.json": json.dumps(deck_json)}})
    # a GLOBAL pref paints both bulk and deck (the fallback layer)
    c.put("/api/prints/Sol Ring",
          json={"image_url": "https://img.test/normal/global.jpg"})
    # a DECK pref wins inside that deck only
    r = c.put("/api/decks/K-1usd/prints/Sol Ring", json={
        "set": "LEA", "collector_number": "1",
        "image_url": "https://img.test/normal/deck.jpg"})
    assert r.status_code == 200, r.text
    detail = c.get("/api/decks/K-1usd").json()
    ring = next(x for x in detail["cards"] if x["name"] == "Sol Ring")
    assert ring["image_url"].endswith("deck.jpg")
    # ...bulk keeps the global choice
    assert c.get("/api/bulk").json()["cards"][0]["image_url"].endswith("global.jpg")
    # the pref landed INSIDE deck_list.json, and the folder was NOT renamed
    saved = json.loads(
        (tmp_path / "library" / "K-1usd" / "deck_list.json").read_text())
    assert saved["print_prefs"]["sol ring"]["set"] == "LEA"
    assert (tmp_path / "library" / "K-1usd").is_dir()
    # GET lists the deck layer only
    assert "sol ring" in c.get("/api/decks/K-1usd/prints").json()
    # the COMMANDER can carry a deck pref too
    r = c.put("/api/decks/K-1usd/prints/krenko, mob boss",
              json={"image_url": "https://img.test/normal/krenko-alt.jpg"})
    assert r.status_code == 200
    detail = c.get("/api/decks/K-1usd").json()
    cmd = next(x for x in detail["cards"] if x["section"] == "commander")
    assert cmd["image_url"].endswith("krenko-alt.jpg")
    # clearing the deck pref FALLS BACK to the global layer
    assert c.delete("/api/decks/K-1usd/prints/Sol Ring").json()["cleared"] is True
    detail = c.get("/api/decks/K-1usd").json()
    ring = next(x for x in detail["cards"] if x["name"] == "Sol Ring")
    assert ring["image_url"].endswith("global.jpg")
    # guards: unknown deck 404; card not in the deck / empty image_url 422
    assert c.put("/api/decks/Nope-1usd/prints/Sol Ring",
                 json={"image_url": "x"}).status_code == 404
    assert c.put("/api/decks/K-1usd/prints/Rhystic Study",
                 json={"image_url": "x"}).status_code == 422
    assert c.put("/api/decks/K-1usd/prints/Sol Ring",
                 json={"image_url": ""}).status_code == 422


def test_deck_print_prefs_survive_edits(monkeypatch, tmp_path):
    import json

    import mtgcli.core.print_prefs as pp_mod
    monkeypatch.setattr(pp_mod, "GUI_PRINTS_PATH", tmp_path / "gui_prints.json")

    c = _client(monkeypatch, tmp_path, decks={
        "K-Test": _seed_deck([{"name": "Sol Ring", "quantity": 1}])})
    c.put("/api/decks/K-Test/prints/Sol Ring",
          json={"set": "LEA", "image_url": "https://img.test/normal/deck.jpg"})
    # PATCH add/remove: prefs ride the Deck round-trip (folder may rename)
    r = c.patch("/api/decks/K-Test/cards", json={"add": ["Mountain"]})
    assert r.status_code == 200, r.text
    name = r.json()["name"]
    dl = _deck_json(c, tmp_path, name)
    assert dl["print_prefs"]["sol ring"]["set"] == "LEA"
    # PUT /list text replace: carried over like config/purposes
    r2 = c.put(f"/api/decks/{name}/list",
               json={"decklist": "1 Sol Ring\n2 Mountain\n"})
    assert r2.status_code == 200, r2.text
    dl2 = _deck_json(c, tmp_path, r2.json()["name"])
    assert dl2["print_prefs"]["sol ring"]["set"] == "LEA"


def test_decks_endpoint_when_library_off(monkeypatch, tmp_path):
    monkeypatch.setattr(gs_mod, "GUI_SETTINGS_PATH", tmp_path / "gui_settings.json")
    gs_mod.save_gui_settings({"builds_save_dir": None})
    c = TestClient(create_app())
    body = c.get("/api/decks").json()
    assert body["dir"] is None and body["decks"] == []


# ── Deck creation + editing (the GUI's manual deckbuilding MVP) ───────────────

def _seed_deck(main_deck, **extra):
    """A library deck folder payload with a Krenko deck_list.json."""
    import json
    data = {"commander": "Krenko, Mob Boss", "main_deck": main_deck, **extra}
    return {"K-Test.txt": "", "deck_list.json": json.dumps(data)}


def _deck_json(c, tmp_path, name):
    import json
    return json.loads(
        (tmp_path / "library" / name / "deck_list.json").read_text())


def test_deck_create_empty(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)
    r = c.post("/api/decks", json={"commander": "krenko, mob boss"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["commander"] == "Krenko, Mob Boss" and body["imported"] == 0
    build_dir = tmp_path / "library" / body["build_name"]
    assert build_dir.is_dir()
    assert _deck_json(c, tmp_path, body["build_name"])["main_deck"] == []
    names = [d["name"] for d in c.get("/api/decks").json()["decks"]]
    assert body["build_name"] in names


def test_deck_create_with_list(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)
    r = c.post("/api/decks", json={
        "commander": "Krenko, Mob Boss",
        "decklist": "1 Sol Ring\n3 Mountain\n1 Not A Real Card\n"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 2 and body["skipped"] == ["Not A Real Card"]
    # bad commander still 422s
    assert c.post("/api/decks", json={"commander": "Sol Ring"}).status_code == 422


def test_deck_edit_add_card_ok(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, decks={
        "K-Test": _seed_deck([{"name": "Mountain", "quantity": 3}])})
    r = c.patch("/api/decks/K-Test/cards", json={"add": ["sol ring"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["added"] == ["Sol Ring"]
    # the folder may have been renamed to fresh tokens — trust the response name
    new = body["name"]
    dl = _deck_json(c, tmp_path, new)
    names = {e["name"] for e in dl["main_deck"]}
    assert names == {"Mountain", "Sol Ring"}
    txt = (tmp_path / "library" / new / f"{new}.txt").read_text()
    assert "1 Sol Ring" in txt and "3 Mountain" in txt


def test_deck_edit_add_rejected_color_identity(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, decks={
        "K-Test": _seed_deck([{"name": "Mountain", "quantity": 3}])})
    r = c.patch("/api/decks/K-Test/cards", json={"add": ["Rhystic Study"]})
    assert r.status_code == 422
    assert "color identity" in r.json()["detail"]["error"]["message"]
    # hard block: nothing written, folder untouched
    dl = _deck_json(c, tmp_path, "K-Test")
    assert {e["name"] for e in dl["main_deck"]} == {"Mountain"}


def test_deck_edit_add_rejected_duplicate(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, decks={
        "K-Test": _seed_deck([{"name": "Sol Ring", "quantity": 1}])})
    r = c.patch("/api/decks/K-Test/cards", json={"add": ["Sol Ring"]})
    assert r.status_code == 422
    assert "singleton" in r.json()["detail"]["error"]["message"]


def test_deck_edit_remove_and_basic_decrement(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, decks={
        "K-Test": _seed_deck([{"name": "Sol Ring", "quantity": 1},
                              {"name": "Mountain", "quantity": 3}])})
    r = c.patch("/api/decks/K-Test/cards", json={"remove": ["Sol Ring"]})
    assert r.status_code == 200, r.text
    name = r.json()["name"]
    dl = _deck_json(c, tmp_path, name)
    assert {e["name"] for e in dl["main_deck"]} == {"Mountain"}
    # basics DECREMENT (deck-remove semantics), nonbasics drop whole
    r2 = c.patch(f"/api/decks/{name}/cards", json={"remove": ["Mountain"]})
    name2 = r2.json()["name"]
    dl2 = _deck_json(c, tmp_path, name2)
    assert dl2["main_deck"][0]["quantity"] == 2
    # empty request -> 422
    assert c.patch(f"/api/decks/{name2}/cards", json={}).status_code == 422


def test_deck_edit_unknown_card_422_with_suggestions(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, decks={"K-Test": _seed_deck([])})
    r = c.patch("/api/decks/K-Test/cards", json={"add": ["Sol Rign"]})
    assert r.status_code == 422
    err = r.json()["detail"]["error"]
    assert "Sol Rign" in err["message"] and "suggestions" in err


def test_deck_replace_list(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, decks={
        "K-Test": _seed_deck([{"name": "Sol Ring", "quantity": 1}])})
    r = c.put("/api/decks/K-Test/list", json={
        "decklist": "1 Krenko, Mob Boss\n2 Mountain\n1 Fake Thing\n"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 1 and body["skipped"] == ["Fake Thing"]
    name = body["name"]
    dl = _deck_json(c, tmp_path, name)
    assert {e["name"] for e in dl["main_deck"]} == {"Mountain"}     # replaced
    txt = (tmp_path / "library" / name / f"{name}.txt").read_text()
    assert "2 Mountain" in txt and "Sol Ring" not in txt
    assert "Krenko" not in txt                                      # command zone
    # nothing resolvable -> 422
    assert c.put(f"/api/decks/{name}/list",
                 json={"decklist": "1 Fake Thing"}).status_code == 422


def test_deck_edit_preserves_annotations(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, decks={
        "K-Test": _seed_deck(
            [{"name": "Sol Ring", "quantity": 1, "purpose": ["RAMP"],
              "agent_note": "keep this"}],
            agent_note="goblin swarm", config={"budget": 50},
            combos={"infinite": [{"cards_needed": ["A", "B"], "how_to": "tap"}]})})
    r = c.patch("/api/decks/K-Test/cards", json={"add": ["Mountain"]})
    assert r.status_code == 200, r.text
    dl = _deck_json(c, tmp_path, r.json()["name"])
    ring = next(e for e in dl["main_deck"] if e["name"] == "Sol Ring")
    assert ring["purpose"] == ["RAMP"] and ring["agent_note"] == "keep this"
    assert dl["agent_note"] == "goblin swarm"
    assert dl["config"] == {"budget": 50}
    assert dl["combos"]["infinite"][0]["cards_needed"] == ["A", "B"]
    # PUT /list carries annotations over BY NAME for surviving cards
    r2 = c.put(f"/api/decks/{r.json()['name']}/list",
               json={"decklist": "1 Sol Ring\n1 Goblin Warchief\n"})
    assert r2.status_code == 200, r2.text
    dl2 = _deck_json(c, tmp_path, r2.json()["name"])
    ring2 = next(e for e in dl2["main_deck"] if e["name"] == "Sol Ring")
    assert ring2["purpose"] == ["RAMP"] and ring2["agent_note"] == "keep this"
    assert dl2["config"] == {"budget": 50}
    assert dl2["combos"]["infinite"][0]["cards_needed"] == ["A", "B"]


def test_deck_edit_legacy_invalid_deck_hard_blocks_then_text_fixes(monkeypatch, tmp_path):
    # an off-color card in the stored JSON: incremental edits refuse honestly...
    c = _client(monkeypatch, tmp_path, decks={
        "K-Test": _seed_deck([{"name": "Rhystic Study", "quantity": 1}])})
    r = c.patch("/api/decks/K-Test/cards", json={"add": ["Sol Ring"]})
    assert r.status_code == 422
    msg = r.json()["detail"]["error"]["message"]
    assert "color identity" in msg and "Edit as text" in msg
    # ...and the text-replace escape hatch recovers the deck
    r2 = c.put("/api/decks/K-Test/list", json={"decklist": "1 Sol Ring\n"})
    assert r2.status_code == 200, r2.text
    name = r2.json()["name"]
    r3 = c.patch(f"/api/decks/{name}/cards", json={"add": ["Mountain"]})
    assert r3.status_code == 200, r3.text


def test_deck_edit_no_deck_list_json_422(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, decks={
        "TxtOnly-1usd": {"TxtOnly-1usd.txt": "1 Sol Ring\n"}})
    r = c.patch("/api/decks/TxtOnly-1usd/cards", json={"add": ["Sol Ring"]})
    assert r.status_code == 422
    assert "deck_list.json" in r.json()["detail"]["error"]["message"]


# ── Workspace-page foundations (sections, color identity, PATCH contract) ────

def test_deck_detail_planeswalker_and_battle_sections(monkeypatch, tmp_path):
    # planeswalker/battle used to fall through to "other" (mapping gap)
    import json
    c = _client(monkeypatch, tmp_path, decks={
        "K-Test": _seed_deck([{"name": "Jaya Ballard", "quantity": 1}])})
    body = c.get("/api/decks/K-Test").json()
    jaya = next(x for x in body["cards"] if x["name"] == "Jaya Ballard")
    assert jaya["section"] == "planeswalkers"
    assert body["stats"]["section_counts"]["planeswalkers"] == 1


def test_deck_detail_color_identity(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, decks={
        "K-Test": _seed_deck([{"name": "Sol Ring", "quantity": 1}])})
    body = c.get("/api/decks/K-Test").json()
    assert body["color_identity"] == ["R"]        # Krenko


def test_deck_detail_color_identity_empty_when_unknown(monkeypatch, tmp_path):
    # txt-only deck (no deck_list.json → no commander metadata) → []
    c = _client(monkeypatch, tmp_path, decks={
        "TxtOnly-1usd": {"TxtOnly-1usd.txt": "1 Sol Ring\n"}})
    assert c.get("/api/decks/TxtOnly-1usd").json()["color_identity"] == []


def test_deck_edit_repeated_names_contract(monkeypatch, tmp_path):
    """The workspace quantity stepper repeats a basic's name N times in one
    PATCH: remove decrements per occurrence, add merges per occurrence."""
    c = _client(monkeypatch, tmp_path, decks={
        "K-Test": _seed_deck([{"name": "Mountain", "quantity": 3}])})
    r = c.patch("/api/decks/K-Test/cards",
                json={"remove": ["Mountain", "Mountain"]})
    assert r.status_code == 200, r.text
    name = r.json()["name"]
    dl = _deck_json(c, tmp_path, name)
    assert dl["main_deck"][0]["quantity"] == 1
    r2 = c.patch(f"/api/decks/{name}/cards",
                 json={"add": ["Mountain", "Mountain"]})
    assert r2.status_code == 200, r2.text
    dl2 = _deck_json(c, tmp_path, r2.json()["name"])
    assert dl2["main_deck"][0]["quantity"] == 3


def test_deck_edit_over_remove_422_not_500(monkeypatch, tmp_path):
    # more repeats than the entry holds → clean atomic 422 (was a crash path)
    c = _client(monkeypatch, tmp_path, decks={
        "K-Test": _seed_deck([{"name": "Mountain", "quantity": 2}])})
    r = c.patch("/api/decks/K-Test/cards",
                json={"remove": ["Mountain", "Mountain", "Mountain"]})
    assert r.status_code == 422
    assert "more copies" in r.json()["detail"]["error"]["message"]
    dl = _deck_json(c, tmp_path, "K-Test")   # untouched (no rename either)
    assert dl["main_deck"][0]["quantity"] == 2


def test_deck_stats_endpoint(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, decks={
        "K-Test": _seed_deck([{"name": "Sol Ring", "quantity": 1},
                              {"name": "Mountain", "quantity": 3}])})
    r = c.get("/api/decks/K-Test/stats")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_cards"] == 5           # 4 main + commander
    assert body["card_type_counts"] == {"artifact": 1, "land": 3}
    # FakeRepo mana_value=1.0 → the one nonland card sits in bucket "1"
    assert body["mana_curve"]["1"] == 1 and body["mana_curve"]["7+"] == 0
    assert body["mana_curve_score"] is not None
    assert body["total_price"] == 0.0          # Sol Ring unpriced in FakeRepo


def test_deck_stats_detail_fields(monkeypatch, tmp_path):
    """v0.9 detail pass: curve extras + color analysis + rank/tier ride along."""
    c = _client(monkeypatch, tmp_path, decks={
        "K-Test": _seed_deck([{"name": "Sol Ring", "quantity": 1},
                              {"name": "Goblin Warchief", "quantity": 1},
                              {"name": "Mountain", "quantity": 3}])})
    body = c.get("/api/decks/K-Test/stats").json()
    # curve extras (FakeRepo hydrates every card at mv=1.0)
    assert body["avg_mv"] == 1.0 and body["median_mv"] == 1.0
    assert body["land_count"] == 3
    assert abs(sum(body["ideal_curve"].values()) - 1.0) < 1e-9
    # color analysis: FakeRepo has no mana_cost/produced_mana → pips/sources 0,
    # but color_cards reads color_identity (Warchief is R)
    assert body["color_cards"]["R"] == 1
    assert body["color_pips"] == {c: 0 for c in "WUBRG"}
    assert body["color_sources"] == {c: 0 for c in "WUBRG"}
    # power metrics: rank reads DB facts; TIER/purposes are annotation-based
    # judgment and deliberately NOT in the workspace stats payload
    assert body["rank"] is None or {"score", "band", "band_name"} <= set(body["rank"])
    assert "tier" not in body and "total_by_purpose" not in body


def test_deck_stats_unloadable_deck_422(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, decks={
        "K-Test": _seed_deck([{"name": "Rhystic Study", "quantity": 1}])})
    r = c.get("/api/decks/K-Test/stats")     # off-color legacy card
    assert r.status_code == 422
    assert "Edit as text" in r.json()["detail"]["error"]["message"]


def test_deck_list_preview_dry_run(monkeypatch, tmp_path):
    import json
    c = _client(monkeypatch, tmp_path, decks={
        "K-Test": _seed_deck([{"name": "Sol Ring", "quantity": 1},
                              {"name": "Mountain", "quantity": 2}])})
    before = (tmp_path / "library" / "K-Test" / "deck_list.json").read_text()
    r = c.post("/api/decks/K-Test/list/preview", json={"decklist": (
        "1 Goblin Warchief\n"
        "2 Mountain\n"              # basic: NOT a duplicate, merges
        "1 Sol Ring\n"              # nonbasic already in deck
        "1 Rhystic Study\n"         # off-color for Krenko
        "1 Totally Fake Card\n"     # unknown
        "1 Goblin Warchief\n"),     # dupe WITHIN the paste
        "mode": "merge"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["skipped"] == ["Totally Fake Card"]
    assert body["already_in_deck"] == ["Sol Ring", "Goblin Warchief"]
    assert body["color_violations"] == ["Rhystic Study"]
    assert body["max_size"] == 99
    # merge applies: Warchief(1) + Mountain(2) → 3 + current 3 = 6
    assert body["projected_size"] == 6
    sections = {e["name"]: e["section"] for e in body["resolved"]}
    assert sections["Mountain"] == "lands"
    # NOTHING persisted (dry-run) — file byte-identical, no rename
    after = (tmp_path / "library" / "K-Test" / "deck_list.json").read_text()
    assert before == after
    # replace mode projects the full pasted list instead
    r2 = c.post("/api/decks/K-Test/list/preview",
                json={"decklist": "1 Goblin Warchief\n2 Mountain\n",
                      "mode": "replace"})
    assert r2.json()["projected_size"] == 3


def test_deck_list_preview_guards(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, decks={
        "K-Test": _seed_deck([]),
        "TxtOnly-1usd": {"TxtOnly-1usd.txt": "1 Sol Ring\n"}})
    assert c.post("/api/decks/K-Test/list/preview",
                  json={"decklist": "1 Sol Ring\n", "mode": "sideways"}
                  ).status_code == 422
    assert c.post("/api/decks/K-Test/list/preview",
                  json={"decklist": "# just a comment\n", "mode": "merge"}
                  ).status_code == 422
    assert c.post("/api/decks/TxtOnly-1usd/list/preview",
                  json={"decklist": "1 Sol Ring\n", "mode": "merge"}
                  ).status_code == 422
    assert c.post("/api/decks/Nope-1usd/list/preview",
                  json={"decklist": "1 Sol Ring\n", "mode": "merge"}
                  ).status_code == 404
