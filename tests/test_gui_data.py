"""Regression: /api/data/refresh — the Download DB / Reload DB button's backend."""
import time

from fastapi.testclient import TestClient

import mtgcli.core.data_refresh as dr_mod
import mtgcli.gui_api.routers.data as data_router
from mtgcli.gui_api.app import create_app


def _client():
    return TestClient(create_app())


def _wait_finished(c, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        j = c.get("/api/data/refresh").json()
        if j["finished"]:
            return j
        time.sleep(0.05)
    raise AssertionError("data refresh never finished")


def test_refresh_download_mode_when_db_missing(monkeypatch, tmp_path):
    seen = {}

    def fake_refresh(*, full, on_phase=None):
        seen["full"] = full
        if on_phase:
            on_phase("building the card database")
        return {"ok": True}

    monkeypatch.setattr(data_router.data_refresh, "refresh_data", fake_refresh)
    monkeypatch.setattr(data_router, "SQLITE_PATH", tmp_path / "missing.sqlite")
    c = _client()
    r = c.post("/api/data/refresh")
    assert r.status_code == 202 and r.json()["mode"] == "download"
    j = _wait_finished(c)
    assert j["error"] is None and seen["full"] is False


def test_refresh_full_mode_when_db_exists(monkeypatch, tmp_path):
    seen = {}
    db = tmp_path / "mtg.sqlite"
    db.write_text("x")
    monkeypatch.setattr(data_router.data_refresh, "refresh_data",
                        lambda *, full, on_phase=None: seen.update(full=full))
    monkeypatch.setattr(data_router, "SQLITE_PATH", db)
    c = _client()
    assert c.post("/api/data/refresh").json()["mode"] == "full"
    _wait_finished(c)
    assert seen["full"] is True


def test_refresh_conflicts(monkeypatch, tmp_path):
    # already running -> 409
    monkeypatch.setattr(data_router, "SQLITE_PATH", tmp_path / "x.sqlite")

    def slow_refresh(*, full, on_phase=None):
        time.sleep(0.5)

    monkeypatch.setattr(data_router.data_refresh, "refresh_data", slow_refresh)
    c = _client()
    assert c.post("/api/data/refresh").status_code == 202
    assert c.post("/api/data/refresh").status_code == 409
    _wait_finished(c)

    # a running BUILD blocks the refresh -> 409
    import threading
    from pathlib import Path
    from mtgcli.gui_api.jobs import Job, JobRegistry
    c2 = _client()
    reg = JobRegistry()
    fake = Job(id="j1", request={"commander": "X"}, provider_name="fake",
               workspace=Path(tmp_path), status="running")
    reg._jobs["j1"] = fake
    c2.app.state.job_registry = reg
    r = c2.post("/api/data/refresh")
    assert r.status_code == 409
    assert "deck build is running" in r.json()["detail"]["error"]["message"]


def test_refresh_error_is_surfaced(monkeypatch, tmp_path):
    def boom(*, full, on_phase=None):
        raise OSError("network down")

    monkeypatch.setattr(data_router.data_refresh, "refresh_data", boom)
    monkeypatch.setattr(data_router, "SQLITE_PATH", tmp_path / "x.sqlite")
    c = _client()
    c.post("/api/data/refresh")
    j = _wait_finished(c)
    assert "network down" in j["error"] and j["phase"] == "failed"


def test_build_blocked_while_data_refresh_runs(tmp_path):
    c = _client()
    c.app.state.data_job = {"running": True, "mode": "full", "phase": "downloading",
                            "started_at": time.monotonic(), "error": None,
                            "finished": False}
    r = c.post("/api/builds", json={"commander": "Krenko, Mob Boss"})
    assert r.status_code == 409
    assert "database is being refreshed" in r.json()["detail"]["error"]["message"]


def test_refresh_service_full_wipes_and_rebuilds(monkeypatch, tmp_path):
    raw = tmp_path / "raw"
    processed = tmp_path / "processed"
    raw.mkdir(); processed.mkdir()
    (raw / "scryfall_cards.json").write_text("old")
    (raw / ".gitkeep").write_text("")
    (processed / "mtg.sqlite").write_text("old")
    monkeypatch.setattr(dr_mod, "RAW_DATA_DIR", raw)
    monkeypatch.setattr(dr_mod, "PROCESSED_DATA_DIR", processed)
    monkeypatch.setattr(dr_mod, "RAW_CARDS_PATH", raw / "scryfall_cards.json")

    import mtgcli.data.download_cards as dl
    import mtgcli.data.build_sqlite as bs
    monkeypatch.setattr(dl, "download_default_cards",
                        lambda: (raw / "scryfall_cards.json").write_text("new"))
    monkeypatch.setattr(bs, "build_sqlite_database", lambda: {"rows": 42})

    phases = []
    out = dr_mod.refresh_data(full=True, on_phase=phases.append)
    assert out["deleted_files"] == 2          # raw json + sqlite; .gitkeep kept
    assert out["downloaded"] is True
    assert (raw / ".gitkeep").exists()
    assert [p.split(" ")[0] for p in phases] == ["deleting", "downloading", "building"]
