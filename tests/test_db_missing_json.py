"""Regression: the "Database not found" pre-check must respect --json-output.

The plain-text pre-check was the last global F2-class hole: every command printed a
rich message under --json-output, breaking agent parsers. All 20 sites now go through
``require_database`` (cli/_shared.py), which emits ``{"error": {"type": "environment"}}``
in JSON mode and keeps the rich text in human mode.
"""
import json

import pytest
from typer.testing import CliRunner

import mtgcli.cli.commands.analysis as analysis_cmd
import mtgcli.cli.commands.cards as cards_cmd
import mtgcli.cli.commands.deck as deck_cmd
import mtgcli.cli.commands.search as search_cmd
from mtgcli.cli import app

runner = CliRunner()


class MissingPath:
    def exists(self):
        return False

    def __str__(self):
        return "/nonexistent/mtg.sqlite"


@pytest.fixture
def no_db(monkeypatch):
    # require_database receives each command module's SQLITE_PATH global, so patching
    # the module (same as the rest of the suite) must keep controlling the check.
    for mod in (cards_cmd, search_cmd, deck_cmd, analysis_cmd):
        monkeypatch.setattr(mod, "SQLITE_PATH", MissingPath())


# One representative command per command module.
CASES = [
    ["card", "Sol Ring"],
    ["search", "draw a card"],
    ["suggest", "--commander", "X", "--role", "ramp"],
    ["deck-check", "--deck", "nope.json", "--commander", "X"],
    ["commander-analyze", "--commander", "X"],
]


@pytest.mark.parametrize("args", CASES, ids=lambda a: a[0])
def test_db_missing_emits_structured_json(no_db, args):
    res = runner.invoke(app, args + ["--json-output"])
    assert res.exit_code == 1
    payload = json.loads(res.stdout)
    assert payload["error"]["type"] == "environment"
    assert "init-data" in payload["error"]["message"]


def test_db_missing_human_mode_unchanged(no_db):
    res = runner.invoke(app, ["card", "Sol Ring"])
    assert res.exit_code == 1
    assert "Database not found" in res.stdout
