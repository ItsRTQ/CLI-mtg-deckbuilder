"""Regression: gui_api skeleton (v0.9.0 Task 3) — /api/health, /api/status, / hint."""
from fastapi.testclient import TestClient

from mtgcli.core.status import project_status
from mtgcli.gui_api.app import create_app


def _client():
    return TestClient(create_app())


def test_health_shape():
    r = _client().get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert isinstance(body["version"], str) and body["version"]


def test_status_mirrors_core_service():
    r = _client().get("/api/status")
    assert r.status_code == 200
    assert r.json() == project_status()


def test_root_returns_frontend_hint_when_dist_absent(monkeypatch, tmp_path):
    # Force a missing dist regardless of the dev machine's state.
    import mtgcli.gui_api.app as app_mod
    monkeypatch.setattr(app_mod, "FRONTEND_DIST", tmp_path / "nope" / "dist")
    r = TestClient(app_mod.create_app()).get("/")
    assert r.status_code == 200
    assert "frontend not built" in r.json()["message"]


def test_spa_fallback_serves_index_when_dist_present(monkeypatch, tmp_path):
    import mtgcli.gui_api.app as app_mod
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>spa</html>")
    (dist / "assets" / "x.js").write_text("js")
    monkeypatch.setattr(app_mod, "FRONTEND_DIST", dist)
    c = TestClient(app_mod.create_app())
    assert "spa" in c.get("/").text
    assert "spa" in c.get("/results").text          # deep link falls back to index
    assert c.get("/assets/x.js").text == "js"       # real files served as-is
    assert c.get("/api/health").status_code == 200  # /api not shadowed
