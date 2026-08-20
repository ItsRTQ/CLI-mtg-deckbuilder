"""Regression: the Tier-2 agent-advice job (POST /api/decks/{name}/advise).

Batch advisory pass on an in-progress draft: the workspace prompt declares the
deck a DRAFT (size/preflight out of scope), and every card the agent suggests
is DB-verified by the job runner (existence + color identity) before the result
reaches the GUI.
"""
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import mtgcli.core.build_workspace as bw_mod
import mtgcli.core.gui_settings as gs_mod
from mtgcli.config import SQLITE_PATH
from mtgcli.core.providers import ProviderManager
from mtgcli.core.providers.base import AgentProvider, ProviderInfo, ProviderResult
from mtgcli.gui_api.app import create_app

needs_db = pytest.mark.skipif(
    not Path(str(SQLITE_PATH)).exists(), reason="card DB not built"
)

TERMINAL = ("succeeded", "failed", "timeout", "cancelled")

RECOMMENDATIONS = {
    "summary": "An early goblin-swarm draft; it wants cheap token payoffs.",
    "recommendations": [{
        "title": "Add token payoffs",
        "priority": "high",
        "reason": "Krenko floods the board; nothing pays it off yet.",
        "cards": [
            {"name": "Impact Tremors", "why": "damage per token", "price_usd": None},
            {"name": "Rhystic Study", "why": "draw", "price_usd": None},   # off-color
            {"name": "Notacardxyz Qqq", "why": "made up", "price_usd": None},
        ],
        "fill": {"tags": ["token_maker"], "query": None, "type": None, "colors": "R"},
    }],
}


class FakeAdviseProvider(AgentProvider):
    name = "fake"
    supports_build = True
    prompt_seen = ""

    def detect(self):
        return ProviderInfo(name="fake", installed=True, supports_build=True)

    def build(self, workspace, prompt_file, *, timeout, cancel_event=None):
        FakeAdviseProvider.prompt_seen = prompt_file.read_text()
        (workspace / "output" / "recommendations.json").write_text(
            json.dumps(RECOMMENDATIONS))
        return ProviderResult(ok=True, exit_code=0)


def _client(monkeypatch, tmp_path, deck_json):
    monkeypatch.setattr(gs_mod, "GUI_SETTINGS_PATH", tmp_path / "gui_settings.json")
    monkeypatch.setattr(bw_mod, "GUI_BUILDS_DIR", tmp_path / "gui-builds")
    lib = tmp_path / "library"
    d = lib / "Draft-Deck"
    d.mkdir(parents=True)
    (d / "deck_list.json").write_text(json.dumps(deck_json), encoding="utf-8")
    gs_mod.save_gui_settings({"builds_save_dir": str(lib)})
    app = create_app()
    c = TestClient(app)
    c.app.state.provider_manager = ProviderManager([FakeAdviseProvider()])
    return c


def _wait_terminal(c, job_id, deadline_s=10):
    deadline = time.monotonic() + deadline_s
    while time.monotonic() < deadline:
        body = c.get(f"/api/builds/{job_id}").json()
        if body["status"] in TERMINAL:
            return body
        time.sleep(0.05)
    return body


@needs_db
def test_advise_runs_on_a_draft_and_verifies_cards(monkeypatch, tmp_path):
    deck_json = {"commander": "Krenko, Mob Boss",
                 "main_deck": [{"name": "Sol Ring", "quantity": 1},
                               {"name": "Mountain", "quantity": 3}]}
    c = _client(monkeypatch, tmp_path, deck_json)
    r = c.post("/api/decks/Draft-Deck/advise", json={"notes": "keep it cheap"})
    assert r.status_code == 202, r.text
    body = _wait_terminal(c, r.json()["job_id"])
    assert body["status"] == "succeeded", body

    # the prompt declared the DRAFT contract (4 cards; no validate/preflight)
    prompt = FakeAdviseProvider.prompt_seen
    assert "DRAFT" in prompt and "4 main-deck cards" in prompt
    assert "keep it cheap" in prompt

    res = body["result"]
    assert res["deck_name"] == "Draft-Deck"
    assert res["summary"].startswith("An early goblin-swarm")
    cards = {card["name"]: card
             for card in res["recommendations"][0]["cards"]}
    assert cards["Impact Tremors"]["valid"] is True
    assert cards["Impact Tremors"]["price_usd"] is not None  # backfilled from DB
    assert cards["Rhystic Study"]["valid"] is False
    assert "color identity" in cards["Rhystic Study"]["issue"]
    made_up = next(card for name, card in cards.items()
                   if name not in ("Impact Tremors", "Rhystic Study"))
    assert made_up["valid"] is False and "not found" in made_up["issue"]


@needs_db
def test_advise_422_without_deck_list_or_commander(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, {"main_deck": []})  # no commander key
    assert c.post("/api/decks/Draft-Deck/advise", json={}).status_code == 422
    assert c.post("/api/decks/Nope/advise", json={}).status_code == 404


@needs_db
def test_advise_fails_honestly_without_deliverable(monkeypatch, tmp_path):
    class NoFileProvider(FakeAdviseProvider):
        def build(self, workspace, prompt_file, *, timeout, cancel_event=None):
            return ProviderResult(ok=True, exit_code=0)   # writes nothing

    deck_json = {"commander": "Krenko, Mob Boss",
                 "main_deck": [{"name": "Sol Ring", "quantity": 1}]}
    c = _client(monkeypatch, tmp_path, deck_json)
    c.app.state.provider_manager = ProviderManager([NoFileProvider()])
    r = c.post("/api/decks/Draft-Deck/advise", json={})
    body = _wait_terminal(c, r.json()["job_id"])
    assert body["status"] == "failed"
    assert body["error"]["type"] == "finish_contract"
