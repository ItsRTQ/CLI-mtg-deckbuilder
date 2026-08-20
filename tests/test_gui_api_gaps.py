"""Regression: the deck-gaps GUI surface (Tier-1 recommendations panel).

- /api/cards/search-tags: the CLI's function-first search exposed to the GUI.
- /api/decks/{name}/gaps: the deck-gaps audit (single source with `mtg
  deck-gaps` via deckbuilder.deck_gaps.compute_deck_gaps) with structured
  `fill` specs the workspace turns into prefilled searches.
"""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mtgcli.config import SQLITE_PATH
from mtgcli.core import gui_settings
from mtgcli.gui_api.app import create_app

needs_db = pytest.mark.skipif(
    not Path(str(SQLITE_PATH)).exists(), reason="card DB not built"
)


def _client():
    return TestClient(create_app())


# ── /api/cards/search-tags ─────────────────────────────────────────────────────

@needs_db
def test_search_tags_returns_ranked_results():
    r = _client().get("/api/cards/search-tags",
                      params={"tags": ["sacrifice_outlet"], "colors": "B",
                              "limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] > 0 and len(body["results"]) <= 5


@needs_db
def test_search_tags_requires_a_nonempty_tag():
    r = _client().get("/api/cards/search-tags", params={"tags": ["  "]})
    assert r.status_code == 422


@needs_db
def test_search_tags_rejects_unknown_type_filter():
    r = _client().get("/api/cards/search-tags",
                      params={"tags": ["ramp"], "type": "notatype"})
    assert r.status_code == 422


# ── /api/decks/{name}/gaps ─────────────────────────────────────────────────────

def _library_with_deck(tmp_path, monkeypatch, *, commander="Krenko, Mob Boss",
                       decklist="1 Sol Ring\n1 Mountain\n"):
    """Point the GUI library at a temp folder holding one thin deck."""
    lib = tmp_path / "final-builds"
    d = lib / "Test-Deck"
    d.mkdir(parents=True)
    (d / "deck_list.json").write_text(json.dumps({
        "commander": commander,
        "main_deck": [
            {"name": ln.split(None, 1)[1], "quantity": int(ln.split(None, 1)[0])}
            for ln in decklist.strip().splitlines()
        ],
    }), encoding="utf-8")
    monkeypatch.setattr(gui_settings, "GUI_SETTINGS_PATH", tmp_path / "gui.json")
    gui_settings.save_gui_settings({"builds_save_dir": str(lib)})
    return d


@needs_db
def test_deck_gaps_reports_thin_deck_with_fill_specs(tmp_path, monkeypatch):
    _library_with_deck(tmp_path, monkeypatch)
    r = _client().get("/api/decks/Test-Deck/gaps", params={"archetype": "tokens"})
    assert r.status_code == 200
    body = r.json()
    assert body["commander"] == "Krenko, Mob Boss"
    assert body["colors"] == "R"
    assert body["gaps"], "a 2-card deck must be thin somewhere"
    g = body["gaps"][0]
    # structured fill spec (the GUI contract) alongside the CLI fill_command
    assert g["fill"]["tags"] == [g["category"]]
    assert g["fill"]["colors"] == "R"
    assert g["fill_command"].startswith("mtg search-tags")
    # analyzer plan check: Krenko reads Go Wide and the deck doesn't serve it
    assert any(pg["archetype"] == "Go Wide" for pg in body["plan_gaps"])


@needs_db
def test_deck_gaps_unknown_deck_404(tmp_path, monkeypatch):
    _library_with_deck(tmp_path, monkeypatch)
    assert _client().get("/api/decks/Nope/gaps").status_code == 404


@needs_db
def test_deck_gaps_without_commander_metadata_422(tmp_path, monkeypatch):
    d = _library_with_deck(tmp_path, monkeypatch)
    (d / "deck_list.json").unlink()
    (d / "Test-Deck.txt").write_text("1 Sol Ring\n", encoding="utf-8")
    r = _client().get("/api/decks/Test-Deck/gaps")
    assert r.status_code == 422
    assert "commander" in r.json()["detail"]["error"]["message"].lower()
