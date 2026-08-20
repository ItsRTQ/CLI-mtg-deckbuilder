"""Regression: /api/builds end-to-end with a FakeProvider (v0.9.0 Task 8).

The workspace files are the contract: the fake provider writes (or omits)
output/final_deck.json + output/explanation.md; the preflight subprocess gate and
the in-process validation are monkeypatched to canned outcomes.
"""
import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

import mtgcli.core.build_workspace as bw_mod
import mtgcli.gui_api.jobs as jobs_mod
from mtgcli.core.providers.base import AgentProvider, ProviderInfo, ProviderResult
from mtgcli.core.providers import ProviderManager
from mtgcli.gui_api.app import create_app
from mtgcli.gui_api.deps import get_repo

KIKI = "Kiki-Jiki, Mirror Breaker"
DECK = {"commander": KIKI,
        "main_deck": [{"name": "Sol Ring", "quantity": 1},
                      {"name": "Mountain", "quantity": 98}]}


class FakeProvider(AgentProvider):
    name = "fake"
    supports_build = True

    def __init__(self, write_deck=True, write_explanation=True, exit_code=0,
                 sleep=0.0, error=None):
        self.write_deck = write_deck
        self.write_explanation = write_explanation
        self.exit_code = exit_code
        self.sleep = sleep
        self.error = error

    def detect(self):
        return ProviderInfo(name=self.name, installed=True, version="fake-1",
                            supports_build=True)

    def build(self, workspace, prompt_file, *, timeout, cancel_event=None):
        (workspace / "logs").mkdir(exist_ok=True)
        (workspace / "logs" / "build.log").write_text(
            "mtg commander-analyze ...\nmtg deck-add ...\n")
        if self.sleep >= timeout:  # emulate the provider tripping its timeout
            return ProviderResult(ok=False, exit_code=-1,
                                  error=f"timeout after {timeout}s")
        deadline = time.monotonic() + self.sleep
        while time.monotonic() < deadline:
            if cancel_event is not None and cancel_event.is_set():
                return ProviderResult(ok=False, exit_code=-1, error="cancelled")
            time.sleep(0.02)
        if self.error:
            return ProviderResult(ok=False, exit_code=self.exit_code or 1,
                                  error=self.error)
        if self.write_deck:
            (workspace / "output" / "final_deck.json").write_text(json.dumps(DECK))
        if self.write_explanation:
            (workspace / "output" / "explanation.md").write_text("# Deck\nnice deck")
        return ProviderResult(ok=(self.exit_code == 0), exit_code=self.exit_code,
                              error=None if self.exit_code == 0 else "boom")


class _FakeRepo:
    def get_card_by_exact_name(self, name):
        if name.lower().startswith("kiki") or name == "Sol Ring" or name == "Mountain":
            return {"name": KIKI if name.lower().startswith("kiki") else name,
                    "can_be_commander": name.lower().startswith("kiki"),
                    "commander_legal": True, "color_identity": ["R"]}
        return None

    def suggest_similar_names(self, name, limit=5):
        return [{"name": KIKI}]


# Registries created by _client — the autouse fixture below JOINS their job
# threads before monkeypatch teardown. Root cause of the "Kiki keeps spawning"
# bug: a test started a job and returned without waiting; the thread outlived
# the isolation patches, read the REAL settings, and auto-saved the fake deck
# (Sol Ring + 98 Mountain) into the user's real final-builds/ on every run.
_REGISTRIES = []


@pytest.fixture(autouse=True)
def _join_job_threads(monkeypatch):
    # Depending on `monkeypatch` guarantees this fixture tears down FIRST
    # (LIFO), so threads finish while the isolation patches are still active.
    yield
    for reg in _REGISTRIES:
        for job in reg.list():
            if job.thread is not None:
                job.thread.join(timeout=10)
    _REGISTRIES.clear()


def _client(provider, monkeypatch, tmp_path, preflight_exit=0, validation_errors=None,
            save_dir=None):
    monkeypatch.setattr(bw_mod, "GUI_BUILDS_DIR", tmp_path / "gui-builds")
    # Isolate the auto-save: never let tests write into the REAL final-builds/.
    import mtgcli.core.gui_settings as gs_mod
    monkeypatch.setattr(gs_mod, "load_gui_settings",
                        lambda **k: {"builds_save_dir": str(save_dir) if save_dir else None})
    monkeypatch.setattr(jobs_mod, "_run_preflight",
                        lambda deck, cmd, **kw: {"ready": preflight_exit == 0,
                                                 "exit_code": preflight_exit})
    # validate_commander_deck is imported inside run_build_job — patch at source.
    import mtgcli.validator.deck_validator as dv
    monkeypatch.setattr(dv, "validate_commander_deck",
                        lambda *a, **k: {"errors": validation_errors or []})
    app = create_app()
    app.state.provider_manager = ProviderManager([provider])
    app.dependency_overrides[get_repo] = lambda: _FakeRepo()
    # pre-create the registry so the thread-join fixture can find every job
    app.state.job_registry = jobs_mod.JobRegistry()
    _REGISTRIES.append(app.state.job_registry)
    return TestClient(app)


def _wait_terminal(client, job_id, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"/api/builds/{job_id}").json()
        if body["status"] in ("succeeded", "failed", "timeout", "cancelled"):
            return body
        time.sleep(0.05)
    raise AssertionError("job never reached a terminal state")


def _start(client, **over):
    payload = {"commander": KIKI, "budget": "150", "bracket": "n/a", **over}
    r = client.post("/api/builds", json=payload)
    assert r.status_code == 202, r.text
    return r.json()["job_id"]


def test_budget_mode_defaults_to_soft(monkeypatch, tmp_path):
    # Old callers that omit the field still work; the payload records soft.
    c = _client(FakeProvider(), monkeypatch, tmp_path)
    job_id = _start(c)  # no budget_mode in payload
    body = _wait_terminal(c, job_id)
    assert body["status"] == "succeeded"


def test_budget_mode_rejects_unknown(monkeypatch, tmp_path):
    c = _client(FakeProvider(), monkeypatch, tmp_path)
    r = c.post("/api/builds", json={"commander": KIKI, "budget": "150",
                                    "bracket": "n/a", "budget_mode": "banana"})
    assert r.status_code == 422


def test_budget_mode_over_requires_pct(monkeypatch, tmp_path):
    c = _client(FakeProvider(), monkeypatch, tmp_path)
    base = {"commander": KIKI, "budget": "150", "bracket": "n/a",
            "budget_mode": "over"}
    assert c.post("/api/builds", json=base).status_code == 422           # missing
    assert c.post("/api/builds", json={**base, "budget_overage_pct": 3}).status_code == 422
    assert c.post("/api/builds", json={**base, "budget_overage_pct": 150}).status_code == 422
    ok = c.post("/api/builds", json={**base, "budget_overage_pct": 25})
    assert ok.status_code == 202, ok.text
    _wait_terminal(c, ok.json()["job_id"])


def test_budget_mode_over_without_numeric_budget_is_inert(monkeypatch, tmp_path):
    # budget n/a -> the mode can't bind to anything; no pct required.
    c = _client(FakeProvider(), monkeypatch, tmp_path)
    r = c.post("/api/builds", json={"commander": KIKI, "budget": "n/a",
                                    "bracket": "n/a", "budget_mode": "over"})
    assert r.status_code == 202, r.text
    _wait_terminal(c, r.json()["job_id"])


def test_happy_path_succeeds_with_result(monkeypatch, tmp_path):
    c = _client(FakeProvider(), monkeypatch, tmp_path)
    job_id = _start(c)
    body = _wait_terminal(c, job_id)
    assert body["status"] == "succeeded", body
    assert body["result"]["commander"] == KIKI
    assert any(e["name"] == "Sol Ring" for e in body["result"]["decklist"])
    assert "nice deck" in body["result"]["explanation"]
    assert body["result"]["preflight"]["ready"] is True


def test_missing_final_deck_fails_finish_contract(monkeypatch, tmp_path):
    c = _client(FakeProvider(write_deck=False), monkeypatch, tmp_path)
    body = _wait_terminal(c, _start(c))
    assert body["status"] == "failed"
    assert body["error"]["type"] == "finish_contract"
    assert "final_deck.json" in body["error"]["message"]


def test_missing_explanation_fails_finish_contract(monkeypatch, tmp_path):
    c = _client(FakeProvider(write_explanation=False), monkeypatch, tmp_path)
    body = _wait_terminal(c, _start(c))
    assert body["status"] == "failed"
    assert "explanation.md" in body["error"]["message"]


def test_provider_nonzero_exit_fails(monkeypatch, tmp_path):
    c = _client(FakeProvider(exit_code=3, error="boom"), monkeypatch, tmp_path)
    body = _wait_terminal(c, _start(c))
    assert body["status"] == "failed" and body["error"]["type"] == "provider"


def test_preflight_gate_failure(monkeypatch, tmp_path):
    c = _client(FakeProvider(), monkeypatch, tmp_path, preflight_exit=1)
    body = _wait_terminal(c, _start(c))
    assert body["status"] == "failed" and body["error"]["type"] == "preflight"


def test_validation_errors_fail_before_preflight(monkeypatch, tmp_path):
    errs = [{"type": "color_identity_violation", "card": "Counterspell"}]
    c = _client(FakeProvider(), monkeypatch, tmp_path, validation_errors=errs)
    body = _wait_terminal(c, _start(c))
    assert body["status"] == "failed" and body["error"]["type"] == "validation"


def test_timeout_path(monkeypatch, tmp_path):
    # FakeProvider trips its timeout when sleep >= timeout (120 >= 60).
    c = _client(FakeProvider(sleep=120), monkeypatch, tmp_path)
    body = _wait_terminal(c, _start(c, timeout_seconds=60), timeout=15)
    assert body["status"] == "timeout"


def test_cancel(monkeypatch, tmp_path):
    c = _client(FakeProvider(sleep=30), monkeypatch, tmp_path)
    job_id = _start(c)
    time.sleep(0.1)
    r = c.post(f"/api/builds/{job_id}/cancel")
    assert r.status_code == 200
    body = _wait_terminal(c, job_id)
    assert body["status"] == "cancelled"


def test_unknown_commander_422_with_suggestions(monkeypatch, tmp_path):
    c = _client(FakeProvider(), monkeypatch, tmp_path)
    r = c.post("/api/builds", json={"commander": "Definitely Not A Card"})
    assert r.status_code == 422
    err = r.json()["detail"]["error"]
    assert err["suggestions"] == [KIKI]


def test_noncommander_card_422(monkeypatch, tmp_path):
    c = _client(FakeProvider(), monkeypatch, tmp_path)
    r = c.post("/api/builds", json={"commander": "Sol Ring"})
    assert r.status_code == 422
    assert "can't be your commander" in r.json()["detail"]["error"]["message"]


def test_no_provider_409(monkeypatch, tmp_path):
    # A detection-only ACTIVE provider is selectable, but the build endpoint
    # refuses with a message pointing back to Settings.
    class _NoBuild(FakeProvider):
        supports_build = False
    c = _client(_NoBuild(), monkeypatch, tmp_path)
    r = c.post("/api/builds", json={"commander": KIKI, "provider": "fake"})
    assert r.status_code == 409
    assert "detection-only" in r.json()["detail"]["error"]["message"]


def test_log_tail_visible_while_running(monkeypatch, tmp_path):
    c = _client(FakeProvider(sleep=2), monkeypatch, tmp_path)
    job_id = _start(c)
    time.sleep(0.3)
    body = c.get(f"/api/builds/{job_id}").json()
    if body["status"] == "running":
        assert any("deck-add" in ln for ln in body["log_tail"])
    _wait_terminal(c, job_id)


def test_unknown_job_404(monkeypatch, tmp_path):
    c = _client(FakeProvider(), monkeypatch, tmp_path)
    assert c.get("/api/builds/nope").status_code == 404
    assert c.post("/api/builds/nope/cancel").status_code == 404


def test_succeeded_build_autosaves_to_configured_library(monkeypatch, tmp_path):
    lib = tmp_path / "my-decks"
    c = _client(FakeProvider(), monkeypatch, tmp_path, save_dir=lib)
    body = _wait_terminal(c, _start(c))
    assert body["status"] == "succeeded"
    saved = body["result"].get("saved_to")
    assert saved and saved.startswith(str(lib))
    from pathlib import Path
    build_dir = Path(saved)
    assert (build_dir / "deck_list.json").exists()
    assert any(p.suffix == ".txt" for p in build_dir.iterdir())      # moxfield list
    assert any(p.name.endswith(".explanation.md") for p in build_dir.iterdir())
    assert build_dir.name.startswith("Kiki-Jiki")                     # library naming


def test_save_failure_is_warning_not_build_failure(monkeypatch, tmp_path):
    # A broken save must NOT fail the build — the deck lives in the workspace.
    import mtgcli.core.save_build as sb_mod

    def _boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(sb_mod, "save_build_to_library", _boom)
    c = _client(FakeProvider(), monkeypatch, tmp_path, save_dir=tmp_path / "lib")
    body = _wait_terminal(c, _start(c))
    assert body["status"] == "succeeded"
    assert "disk full" in body["result"]["save_warning"]
    assert "saved_to" not in body["result"]


def test_one_build_at_a_time_409_while_running(monkeypatch, tmp_path):
    c = _client(FakeProvider(sleep=3), monkeypatch, tmp_path)
    first = _start(c)
    # second build while the first runs -> 409 conflict pointing at the job
    r = c.post("/api/builds", json={"commander": KIKI})
    assert r.status_code == 409
    err = r.json()["detail"]["error"]
    assert err["type"] == "conflict" and err["job_id"] == first
    assert "already running" in err["message"]
    # after the first finishes, a new build is allowed again — and we WAIT for
    # it: a job thread left running would outlive this test's monkeypatches
    # (the original "Kiki keeps spawning into final-builds/" bug)
    _wait_terminal(c, first)
    r2 = c.post("/api/builds", json={"commander": KIKI})
    assert r2.status_code == 202
    _wait_terminal(c, r2.json()["job_id"])


def test_list_builds_recovers_jobs_newest_first(monkeypatch, tmp_path):
    # The UI's route-change recovery: builds live server-side, GET /api/builds
    # finds them again (newest first, with commander + status).
    c = _client(FakeProvider(), monkeypatch, tmp_path)
    assert c.get("/api/builds").json() == []
    first = _start(c)
    _wait_terminal(c, first)
    second = _start(c)
    _wait_terminal(c, second)
    jobs = c.get("/api/builds").json()
    assert [j["job_id"] for j in jobs] == [second, first]
    assert jobs[0]["commander"] == KIKI
    assert all(j["status"] == "succeeded" for j in jobs)
