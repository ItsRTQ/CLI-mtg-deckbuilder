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


def test_gui_port_in_use_exits_one(monkeypatch):
    _patch(monkeypatch)
    import uvicorn

    def _boom(*a, **k):
        raise OSError("address already in use")

    monkeypatch.setattr(uvicorn, "run", _boom)
    r = runner.invoke(app, ["gui", "--no-browser"])
    assert r.exit_code == 1
    assert "Could not bind" in r.output
