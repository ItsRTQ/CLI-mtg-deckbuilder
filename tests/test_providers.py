"""Regression: core.providers + /api/providers (v0.9.0 Task 7)."""
import subprocess
import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import mtgcli.core.providers.claude_code as cc_mod
import mtgcli.core.providers.ollama as ol_mod
from mtgcli.core.providers import (
    ClaudeCodeProvider,
    OllamaProvider,
    ProviderBuildUnsupported,
    ProviderManager,
)
from mtgcli.gui_api.app import create_app


# ── ClaudeCodeProvider.detect ──────────────────────────────────────────────────

def test_claude_detect_missing(monkeypatch):
    monkeypatch.setattr(cc_mod.shutil, "which", lambda _: None)
    info = ClaudeCodeProvider().detect()
    assert info.installed is False and info.supports_build is True


def test_claude_detect_version(monkeypatch):
    monkeypatch.setattr(cc_mod.shutil, "which", lambda _: "/usr/bin/claude")
    monkeypatch.setattr(cc_mod.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(stdout="2.1.206 (Claude Code)\n",
                                                        stderr=""))
    info = ClaudeCodeProvider().detect()
    assert info.installed is True and info.version.startswith("2.1.206")


def test_claude_detect_timeout(monkeypatch):
    monkeypatch.setattr(cc_mod.shutil, "which", lambda _: "/usr/bin/claude")

    def _boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=10)

    monkeypatch.setattr(cc_mod.subprocess, "run", _boom)
    assert ClaudeCodeProvider().detect().installed is False


# ── ClaudeCodeProvider.build ───────────────────────────────────────────────────

class _FakeProc:
    def __init__(self, exit_code=0, hang=False):
        self.exit_code = exit_code
        self.hang = hang
        self.pid = 4242
        self.killed = False
        self._polls = 0

    def poll(self):
        if self.hang and not self.killed:
            return None
        self._polls += 1
        return None if self._polls < 2 else self.exit_code

    @property
    def returncode(self):
        return self.exit_code

    def kill(self):
        self.killed = True


def _prompt(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    p = ws / "agent_prompt.md"
    p.write_text("build the deck")
    return ws, p


def test_claude_build_argv_tight_permissions(monkeypatch, tmp_path):
    ws, prompt = _prompt(tmp_path)
    seen = {}

    def fake_popen(argv, **kwargs):
        seen["argv"] = argv
        seen["cwd"] = kwargs.get("cwd")
        seen["start_new_session"] = kwargs.get("start_new_session")
        return _FakeProc(exit_code=0)

    monkeypatch.setattr(cc_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(cc_mod.time, "sleep", lambda _: None)
    res = ClaudeCodeProvider().build(ws, prompt, timeout=60)
    assert res.ok and res.exit_code == 0
    argv = seen["argv"]
    assert argv[:2] == ["claude", "-p"] and argv[2] == "build the deck"
    # stream-json + --verbose: line-by-line events keep logs/build.log live
    # (plain "json" buffers to the end — the GUI would look frozen).
    assert "--output-format" in argv and "stream-json" in argv and "--verbose" in argv
    assert "--allowedTools" in argv
    allowed = argv[argv.index("--allowedTools") + 1]
    assert "Bash(mtg *)" in allowed and "Edit" not in allowed
    assert "--dangerously-skip-permissions" not in argv
    assert seen["cwd"] == ws and seen["start_new_session"] is True
    assert (ws / "logs" / "build.log").exists()


def test_claude_build_unsafe_flag_optin(monkeypatch, tmp_path):
    ws, prompt = _prompt(tmp_path)
    seen = {}
    monkeypatch.setattr(cc_mod.subprocess, "Popen",
                        lambda argv, **k: seen.update(argv=argv) or _FakeProc())
    monkeypatch.setattr(cc_mod.time, "sleep", lambda _: None)
    ClaudeCodeProvider().build(ws, prompt, timeout=60, unsafe_skip_permissions=True)
    assert "--dangerously-skip-permissions" in seen["argv"]
    assert "--allowedTools" not in seen["argv"]


def test_claude_build_timeout_kills(monkeypatch, tmp_path):
    ws, prompt = _prompt(tmp_path)
    proc = _FakeProc(hang=True)
    monkeypatch.setattr(cc_mod.subprocess, "Popen", lambda *a, **k: proc)
    monkeypatch.setattr(cc_mod.time, "sleep", lambda _: None)
    clock = iter(range(0, 10_000, 100))
    monkeypatch.setattr(cc_mod.time, "monotonic", lambda: next(clock))
    killed = []
    monkeypatch.setattr(ClaudeCodeProvider, "_kill",
                        staticmethod(lambda p: killed.append(p)))
    res = ClaudeCodeProvider().build(ws, prompt, timeout=50)
    assert res.ok is False and "timeout" in res.error
    assert killed == [proc]


def test_claude_build_cancel_kills(monkeypatch, tmp_path):
    ws, prompt = _prompt(tmp_path)
    proc = _FakeProc(hang=True)
    monkeypatch.setattr(cc_mod.subprocess, "Popen", lambda *a, **k: proc)
    monkeypatch.setattr(cc_mod.time, "sleep", lambda _: None)
    killed = []
    monkeypatch.setattr(ClaudeCodeProvider, "_kill",
                        staticmethod(lambda p: killed.append(p)))
    ev = threading.Event()
    ev.set()
    res = ClaudeCodeProvider().build(ws, prompt, timeout=60, cancel_event=ev)
    assert res.ok is False and res.error == "cancelled" and killed == [proc]


# ── Ollama ─────────────────────────────────────────────────────────────────────

def test_ollama_detect_and_build_unsupported(monkeypatch, tmp_path):
    monkeypatch.setattr(ol_mod.shutil, "which", lambda _: "/usr/bin/ollama")

    class _Resp:
        def json(self):
            return {"models": [{"name": "llama3"}]}

    monkeypatch.setattr(ol_mod.requests, "get", lambda *a, **k: _Resp())
    info = OllamaProvider().detect()
    assert info.installed is True and "llama3" in info.detail
    assert info.supports_build is False
    with pytest.raises(ProviderBuildUnsupported):
        OllamaProvider().build(tmp_path, tmp_path / "x.md", timeout=1)


def test_ollama_detect_missing(monkeypatch):
    monkeypatch.setattr(ol_mod.shutil, "which", lambda _: None)
    assert OllamaProvider().detect().installed is False


# ── Antigravity ────────────────────────────────────────────────────────────────

def test_antigravity_detects_agy_binary(monkeypatch):
    import mtgcli.core.providers.antigravity as ag_mod
    from mtgcli.core.providers import AntigravityProvider

    # the binary is `agy`, NOT `antigravity`
    monkeypatch.setattr(ag_mod.shutil, "which",
                        lambda name: "/home/u/.local/bin/agy" if name == "agy" else None)
    monkeypatch.setattr(ag_mod.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(stdout="1.1.0\n", stderr=""))
    info = AntigravityProvider().detect()
    assert info.installed is True and info.version == "1.1.0"
    assert info.supports_build is True


def test_antigravity_missing_and_version_failure_tolerated(monkeypatch):
    import mtgcli.core.providers.antigravity as ag_mod
    from mtgcli.core.providers import AntigravityProvider

    monkeypatch.setattr(ag_mod.shutil, "which", lambda _: None)
    assert AntigravityProvider().detect().installed is False

    # installed but --version times out -> still installed, version None
    monkeypatch.setattr(ag_mod.shutil, "which", lambda _: "/usr/bin/agy")

    def _boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="agy", timeout=10)

    monkeypatch.setattr(ag_mod.subprocess, "run", _boom)
    info = AntigravityProvider().detect()
    assert info.installed is True and info.version is None


def test_antigravity_build_argv_add_dir_and_print_timeout(monkeypatch, tmp_path):
    import mtgcli.core.providers.antigravity as ag_mod
    from mtgcli.core.providers import AntigravityProvider

    ws, prompt = _prompt(tmp_path)
    seen = {}

    def fake_popen(argv, **kwargs):
        seen["argv"] = argv
        seen["cwd"] = kwargs.get("cwd")
        seen["start_new_session"] = kwargs.get("start_new_session")
        return _FakeProc(exit_code=0)

    monkeypatch.setattr(ag_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(ag_mod.time, "sleep", lambda _: None)
    res = AntigravityProvider().build(ws, prompt, timeout=900)
    assert res.ok and res.exit_code == 0
    argv = seen["argv"]
    assert argv[0] == "agy"
    # --add-dir <workspace> is REQUIRED: agy print mode ignores cwd (measured)
    assert argv[argv.index("--add-dir") + 1] == str(ws)
    assert argv[argv.index("-p") + 1] == "build the deck"
    # --print-timeout must cover the build (agy default 5m is too short)
    assert argv[argv.index("--print-timeout") + 1] == "900s"
    assert "--dangerously-skip-permissions" not in argv  # not needed (measured)
    assert seen["cwd"] == ws and seen["start_new_session"] is True
    assert (ws / "logs" / "build.log").exists()


def test_antigravity_build_timeout_and_cancel_kill(monkeypatch, tmp_path):
    import mtgcli.core.providers.antigravity as ag_mod
    from mtgcli.core.providers import AntigravityProvider

    ws, prompt = _prompt(tmp_path)
    killed = []
    monkeypatch.setattr(ag_mod, "kill_process_group", lambda p: killed.append(p))
    monkeypatch.setattr(ag_mod.time, "sleep", lambda _: None)

    proc = _FakeProc(hang=True)
    monkeypatch.setattr(ag_mod.subprocess, "Popen", lambda *a, **k: proc)
    clock = iter(range(0, 100_000, 100))
    monkeypatch.setattr(ag_mod.time, "monotonic", lambda: next(clock))
    res = AntigravityProvider().build(ws, prompt, timeout=50)
    assert res.ok is False and "timeout" in res.error and killed == [proc]

    killed.clear()
    proc2 = _FakeProc(hang=True)
    monkeypatch.setattr(ag_mod.subprocess, "Popen", lambda *a, **k: proc2)
    ev = threading.Event()
    ev.set()
    res = AntigravityProvider().build(ws, prompt, timeout=60, cancel_event=ev)
    assert res.error == "cancelled" and killed == [proc2]


def test_default_manager_registers_antigravity():
    from mtgcli.core.providers import ProviderManager
    mgr = ProviderManager()
    assert mgr.get("antigravity") is not None
    assert mgr.get("claude-code") is not None and mgr.get("ollama") is not None


# ── Codex ──────────────────────────────────────────────────────────────────────

def test_codex_detect(monkeypatch):
    import mtgcli.core.providers.codex as cx_mod
    from mtgcli.core.providers import CodexProvider

    monkeypatch.setattr(cx_mod.shutil, "which", lambda _: None)
    assert CodexProvider().detect().installed is False

    monkeypatch.setattr(cx_mod.shutil, "which", lambda _: "/usr/bin/codex")
    monkeypatch.setattr(cx_mod.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(stdout="codex-cli 0.144.1\n",
                                                        stderr=""))
    info = CodexProvider().detect()
    assert info.installed is True and info.version == "codex-cli 0.144.1"
    assert info.supports_build is True


def test_codex_build_argv_sandbox_and_stdin_devnull(monkeypatch, tmp_path):
    import mtgcli.core.providers.codex as cx_mod
    from mtgcli.core.providers import CodexProvider

    ws, prompt = _prompt(tmp_path)
    seen = {}

    def fake_popen(argv, **kwargs):
        seen["argv"] = argv
        seen["cwd"] = kwargs.get("cwd")
        seen["stdin"] = kwargs.get("stdin")
        seen["start_new_session"] = kwargs.get("start_new_session")
        return _FakeProc(exit_code=0)

    monkeypatch.setattr(cx_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(cx_mod.time, "sleep", lambda _: None)
    res = CodexProvider().build(ws, prompt, timeout=900)
    assert res.ok and res.exit_code == 0
    argv = seen["argv"]
    assert argv[:3] == ["codex", "exec", "--skip-git-repo-check"]
    assert "--ephemeral" in argv
    # codex's own sandbox IS our contract: writes confined to the workspace
    assert argv[argv.index("-s") + 1] == "workspace-write"
    # env inherit so the venv's `mtg` resolves inside codex's shells (measured)
    assert 'shell_environment_policy.inherit="all"' in argv
    assert argv[-1] == "build the deck"
    assert "--dangerously-bypass-approvals-and-sandbox" not in argv
    # THE measured failure mode: a piped stdin makes codex wait for EOF forever
    assert seen["stdin"] is cx_mod.subprocess.DEVNULL
    assert seen["cwd"] == ws and seen["start_new_session"] is True


def test_codex_build_timeout_and_cancel_kill(monkeypatch, tmp_path):
    import mtgcli.core.providers.codex as cx_mod
    from mtgcli.core.providers import CodexProvider

    ws, prompt = _prompt(tmp_path)
    killed = []
    monkeypatch.setattr(cx_mod, "kill_process_group", lambda p: killed.append(p))
    monkeypatch.setattr(cx_mod.time, "sleep", lambda _: None)

    proc = _FakeProc(hang=True)
    monkeypatch.setattr(cx_mod.subprocess, "Popen", lambda *a, **k: proc)
    clock = iter(range(0, 100_000, 100))
    monkeypatch.setattr(cx_mod.time, "monotonic", lambda: next(clock))
    res = CodexProvider().build(ws, prompt, timeout=50)
    assert res.ok is False and "timeout" in res.error and killed == [proc]

    killed.clear()
    proc2 = _FakeProc(hang=True)
    monkeypatch.setattr(cx_mod.subprocess, "Popen", lambda *a, **k: proc2)
    ev = threading.Event()
    ev.set()
    res = CodexProvider().build(ws, prompt, timeout=60, cancel_event=ev)
    assert res.error == "cancelled" and killed == [proc2]


def test_default_manager_registers_codex():
    from mtgcli.core.providers import ProviderManager
    assert ProviderManager().get("codex") is not None


# ── Manager + API ──────────────────────────────────────────────────────────────

class _StubProvider:
    def __init__(self, name, installed, supports_build=True):
        self.name = name
        self.supports_build = supports_build
        self._installed = installed

    def detect(self):
        from mtgcli.core.providers.base import ProviderInfo
        return ProviderInfo(name=self.name, installed=self._installed,
                            supports_build=self.supports_build)

    def build(self, *a, **k):
        raise NotImplementedError


def test_manager_default_prefers_installed_build_capable():
    mgr = ProviderManager([_StubProvider("a", installed=False),
                           _StubProvider("b", installed=True),
                           _StubProvider("c", installed=True, supports_build=False)])
    assert mgr.default_build_provider() == "b"
    assert ProviderManager([_StubProvider("x", False)]).default_build_provider() is None


def _client_with(providers):
    app = create_app()
    app.state.provider_manager = ProviderManager(providers)
    return TestClient(app)


def test_providers_endpoint_lists_and_selects():
    c = _client_with([_StubProvider("claude-code", installed=True),
                      _StubProvider("ollama", installed=False, supports_build=False)])
    r = c.get("/api/providers")
    assert r.status_code == 200
    by_name = {p["name"]: p for p in r.json()}
    assert by_name["claude-code"]["selected"] is True  # default = installed+build
    assert by_name["ollama"]["installed"] is False
    ok = c.post("/api/providers/select", json={"name": "claude-code"})
    assert ok.status_code == 200
    assert c.post("/api/providers/select", json={"name": "nope"}).status_code == 404
    # NOT installed -> still refused
    assert c.post("/api/providers/select", json={"name": "ollama"}).status_code == 409


def test_installed_detection_only_provider_is_selectable_but_cannot_build():
    # The user owns the choice: an INSTALLED detection-only provider can be made
    # active by clicking it; the BUILD endpoint is the gate that refuses (409).
    c = _client_with([_StubProvider("claude-code", installed=True),
                      _StubProvider("antigravity", installed=True,
                                    supports_build=False)])
    r = c.post("/api/providers/select", json={"name": "antigravity"})
    assert r.status_code == 200
    by_name = {p["name"]: p for p in r.json()}
    assert by_name["antigravity"]["selected"] is True
    assert by_name["claude-code"]["selected"] is False
