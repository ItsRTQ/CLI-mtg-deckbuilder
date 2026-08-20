"""Regression: gui_api deck export endpoint — GET /api/decks/{name}/export/tcgplayer."""
import json

from fastapi.testclient import TestClient

import mtgcli.gui_api.routers.library as library_mod
from mtgcli.export.tcgplayer import build_tcgplayer_mass_entry_url
from mtgcli.gui_api.app import create_app
from mtgcli.gui_api.deps import get_repo_optional


def _client(monkeypatch, lib_dir, repo=None):
    monkeypatch.setattr(library_mod, "_library_dir", lambda: lib_dir)
    app = create_app()
    app.dependency_overrides[get_repo_optional] = lambda: repo
    return TestClient(app)


def _make_deck(lib_dir, name, deck_list=None, txt=None):
    d = lib_dir / name
    d.mkdir(parents=True)
    if deck_list is not None:
        (d / "deck_list.json").write_text(json.dumps(deck_list), encoding="utf-8")
    if txt is not None:
        (d / f"{name}.txt").write_text(txt, encoding="utf-8")
    return d


def test_export_includes_commander_and_entries(tmp_path, monkeypatch):
    _make_deck(tmp_path, "MyDeck", deck_list={
        "commanders": ["Shorikai, Genesis Engine"],
        "main_deck": [{"name": "Sol Ring", "quantity": 1},
                      {"name": "Command Tower", "quantity": 1}],
    })
    r = _client(monkeypatch, tmp_path).get("/api/decks/MyDeck/export/tcgplayer")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["entries"] == 3
    assert data["url"] == build_tcgplayer_mass_entry_url([
        {"name": "Shorikai, Genesis Engine", "quantity": 1},
        {"name": "Sol Ring", "quantity": 1},
        {"name": "Command Tower", "quantity": 1},
    ])
    assert "Shorikai%2C+Genesis+Engine" in data["url"]


def test_export_txt_fallback_without_deck_list_json(tmp_path, monkeypatch):
    _make_deck(tmp_path, "TxtDeck", txt="1 Sol Ring\n2 Mountain\n")
    r = _client(monkeypatch, tmp_path).get("/api/decks/TxtDeck/export/tcgplayer")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["entries"] == 2
    assert "2+Mountain" in data["url"]


class _LayoutRepo:
    def __init__(self, layouts):
        self.layouts = layouts

    def get_card_by_exact_name(self, name):
        layout = self.layouts.get(name)
        return {"name": name, "layout": layout} if layout else None


def test_export_split_keeps_full_name_via_repo(tmp_path, monkeypatch):
    _make_deck(tmp_path, "Splits", deck_list={
        "commanders": [],
        "main_deck": [{"name": "Wear // Tear", "quantity": 1},
                      {"name": "Delver of Secrets // Insectile Aberration", "quantity": 1}],
    })
    repo = _LayoutRepo({"Wear // Tear": "split",
                        "Delver of Secrets // Insectile Aberration": "transform"})
    r = _client(monkeypatch, tmp_path, repo=repo).get("/api/decks/Splits/export/tcgplayer")
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert "Wear+%2F%2F+Tear" in url          # split keeps "A // B"
    assert "Delver+of+Secrets" in url and "Insectile" not in url  # transform → front face


def test_export_unknown_deck_404(tmp_path, monkeypatch):
    r = _client(monkeypatch, tmp_path).get("/api/decks/Nope/export/tcgplayer")
    assert r.status_code == 404


def test_export_empty_deck_422(tmp_path, monkeypatch):
    _make_deck(tmp_path, "Empty", deck_list={"commanders": [], "main_deck": []})
    r = _client(monkeypatch, tmp_path).get("/api/decks/Empty/export/tcgplayer")
    assert r.status_code == 422
    err = r.json()["detail"]["error"]
    assert err["type"] == "validation"
