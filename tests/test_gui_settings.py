"""Regression: gui settings (builds_save_dir) — service + /api/settings."""
import pytest
from fastapi.testclient import TestClient

import mtgcli.core.gui_settings as gs_mod
from mtgcli.core.gui_settings import (
    load_gui_settings,
    resolve_save_dir,
    save_gui_settings,
)
from mtgcli.gui_api.app import create_app


def test_settings_roundtrip_and_defaults(tmp_path):
    p = tmp_path / "gui_settings.json"
    s = load_gui_settings(path=p)                 # no file -> defaults
    assert s["builds_save_dir"]                    # default = final-builds library
    save_gui_settings({"builds_save_dir": str(tmp_path / "decks")}, path=p)
    assert load_gui_settings(path=p)["builds_save_dir"] == str(tmp_path / "decks")
    save_gui_settings({"builds_save_dir": None}, path=p)   # clear = don't save
    assert load_gui_settings(path=p)["builds_save_dir"] is None


def test_resolve_save_dir_rules(tmp_path):
    assert resolve_save_dir(None) is None
    assert resolve_save_dir("   ") is None
    # relative resolves against the project root
    from mtgcli.config import PROJECT_ROOT
    assert resolve_save_dir("final-builds") == PROJECT_ROOT / "final-builds"
    # absolute is created + write-probed
    target = tmp_path / "new" / "nested"
    assert resolve_save_dir(str(target)) == target and target.is_dir()
    # a FILE at the path is rejected
    f = tmp_path / "afile"
    f.write_text("x")
    with pytest.raises(ValueError):
        resolve_save_dir(str(f))


def test_browse_endpoint_lists_directories(tmp_path):
    (tmp_path / "decks").mkdir()
    (tmp_path / "zeta").mkdir()
    (tmp_path / ".hidden").mkdir()          # hidden dirs excluded
    (tmp_path / "afile.txt").write_text("x")  # files excluded
    c = TestClient(create_app())
    r = c.get("/api/settings/browse", params={"path": str(tmp_path)})
    assert r.status_code == 200
    body = r.json()
    assert body["path"] == str(tmp_path)
    assert body["dirs"] == ["decks", "zeta"]
    assert body["parent"] == str(tmp_path.parent)
    assert body["writable"] is True
    # descending into a child works; a file path is a 422
    child = c.get("/api/settings/browse", params={"path": str(tmp_path / "decks")})
    assert child.status_code == 200 and child.json()["dirs"] == []
    bad = c.get("/api/settings/browse", params={"path": str(tmp_path / "afile.txt")})
    assert bad.status_code == 422
    # no path -> home
    home = c.get("/api/settings/browse")
    assert home.status_code == 200
    from pathlib import Path
    assert home.json()["path"] == str(Path.home())


def test_settings_endpoint_get_post_validate(tmp_path, monkeypatch):
    monkeypatch.setattr(gs_mod, "GUI_SETTINGS_PATH", tmp_path / "gui_settings.json")
    c = TestClient(create_app())
    r = c.get("/api/settings")
    assert r.status_code == 200 and r.json()["builds_save_dir"]
    ok = c.post("/api/settings", json={"builds_save_dir": str(tmp_path / "lib")})
    assert ok.status_code == 200
    assert ok.json()["builds_save_dir_resolved"] == str(tmp_path / "lib")
    # invalid (a file) -> 422 with the JSON error contract
    f = tmp_path / "f.txt"
    f.write_text("x")
    bad = c.post("/api/settings", json={"builds_save_dir": str(f)})
    assert bad.status_code == 422
    assert bad.json()["detail"]["error"]["type"] == "validation"
    # clearing works
    cleared = c.post("/api/settings", json={"builds_save_dir": ""})
    assert cleared.status_code == 200 and cleared.json()["builds_save_dir"] is None


def test_user_bulk_dir_setting_and_partial_updates(tmp_path, monkeypatch):
    monkeypatch.setattr(gs_mod, "GUI_SETTINGS_PATH", tmp_path / "gui_settings.json")
    c = TestClient(create_app())
    # default: unset -> resolved shows the project's user-bulk/
    r = c.get("/api/settings").json()
    assert r["user_bulk_dir"] is None
    from mtgcli.config import USER_BULK_DIR
    assert r["user_bulk_dir_resolved"] == str(USER_BULK_DIR)
    # set a custom collection folder
    bulk = tmp_path / "my-collection"
    ok = c.post("/api/settings", json={"user_bulk_dir": str(bulk)}).json()
    assert ok["user_bulk_dir"] == str(bulk)
    assert ok["user_bulk_dir_resolved"] == str(bulk)
    # PARTIAL update: posting only builds_save_dir must NOT clobber user_bulk_dir
    c.post("/api/settings", json={"builds_save_dir": str(tmp_path / "lib")})
    after = c.get("/api/settings").json()
    assert after["user_bulk_dir"] == str(bulk)
    # and the loader actually reads collection.txt from the custom folder
    import mtgcli.deckbuilder.user_bulk as ub
    bulk.mkdir(exist_ok=True)
    (bulk / "collection.txt").write_text("Rhystic Study\nSmothering Tithe\n")
    assert ub.default_bulk_file() == bulk / "collection.txt"
    owned = ub.load_user_bulk()
    assert "Rhystic Study" in owned and "Smothering Tithe" in owned
    # clearing goes back to the project default
    c.post("/api/settings", json={"user_bulk_dir": ""})
    assert ub.default_bulk_file() == ub.USER_BULK_FILE