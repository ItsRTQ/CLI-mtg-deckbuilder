"""Regression: `mtg gui` (v0.9.0 Task 4) — server launch + browser, no real binding."""
from typer.testing import CliRunner

import mtgcli.cli.commands.gui as gui_mod
from mtgcli.cli import app

runner = CliRunner()


class _Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))


def _patch(monkeypatch):
    """Patch uvicorn.run and the browser timer at their use sites."""
    run = _Recorder()
    opened = _Recorder()
    import uvicorn
    import webbrowser
    monkeypatch.setattr(uvicorn, "run", run)
    monkeypatch.setattr(webbrowser, "open", opened)

    # Make the browser Timer fire synchronously so the test needs no sleep.
    import threading

    class _InstantTimer:
        def __init__(self, interval, fn, args=()):
            self.fn, self.args = fn, args

        def start(self):
            self.fn(*self.args)

    monkeypatch.setattr(threading, "Timer", _InstantTimer)
    return run, opened


def test_gui_passes_host_port_and_opens_browser(monkeypatch):
    run, opened = _patch(monkeypatch)
    r = runner.invoke(app, ["gui", "--host", "0.0.0.0", "--port", "9999"])
    assert r.exit_code == 0, r.output
    assert run.calls, "uvicorn.run was not called"
    _, kwargs = run.calls[0]
    assert kwargs["host"] == "0.0.0.0" and kwargs["port"] == 9999
    assert opened.calls and opened.calls[0][0][0] == "http://0.0.0.0:9999/"


def test_gui_no_browser_suppresses_open(monkeypatch):
    run, opened = _patch(monkeypatch)
    r = runner.invoke(app, ["gui", "--no-browser"])
    assert r.exit_code == 0, r.output
    assert run.calls and not opened.calls


def test_gui_rebuild_runs_npm_build_before_serving(monkeypatch, tmp_path):
    run, _ = _patch(monkeypatch)
    import shutil
    import subprocess

    from mtgcli import config as config_mod

    (tmp_path / "gui").mkdir()
    (tmp_path / "gui" / "package.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(config_mod, "FRONTEND_DIST", tmp_path / "gui" / "dist")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/npm")
    built = _Recorder()

    class _Done:
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (built(*a, **k), _Done())[1])
    r = runner.invoke(app, ["gui", "--rebuild", "--no-browser"])
    assert r.exit_code == 0, r.output
    assert built.calls, "npm run build was not invoked"
    args, kwargs = built.calls[0]
    assert args[0][-2:] == ["run", "build"] and kwargs["cwd"] == tmp_path / "gui"
    assert run.calls, "server did not start after the rebuild"


def test_gui_rebuild_without_npm_exits_one(monkeypatch):
    _patch(monkeypatch)
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: None)
    r = runner.invoke(app, ["gui", "--rebuild", "--no-browser"])
    assert r.exit_code == 1
    assert "npm not found" in r.output


def test_gui_rebuild_failure_exits_one(monkeypatch, tmp_path):
    run, _ = _patch(monkeypatch)
    import shutil
    import subprocess

    from mtgcli import config as config_mod

    (tmp_path / "gui").mkdir()
    (tmp_path / "gui" / "package.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(config_mod, "FRONTEND_DIST", tmp_path / "gui" / "dist")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/npm")

    class _Fail:
        returncode = 1

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Fail())
    r = runner.invoke(app, ["gui", "--rebuild", "--no-browser"])
    assert r.exit_code == 1
    assert "build failed" in r.output
    assert not run.calls, "server must not start after a failed rebuild"


def test_gui_port_in_use_exits_one(monkeypatch):
    _patch(monkeypatch)
    import uvicorn

    def _boom(*a, **k):
        raise OSError("address already in use")

    monkeypatch.setattr(uvicorn, "run", _boom)
    r = runner.invoke(app, ["gui", "--no-browser"])
    assert r.exit_code == 1
    assert "Could not bind" in r.output
