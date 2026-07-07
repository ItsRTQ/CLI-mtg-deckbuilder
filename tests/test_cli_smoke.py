"""Smoke tests for the ``mtgcli.cli`` package (split from the former single
``cli.py``). The monolith had no direct unit tests; these guard the split:

* every registered command answers ``--help`` with exit 0,
* the exact public command set is registered (catches a command that failed to
  register because its module was not imported, or a rename),
* ``--help`` lists commands in the original order (the split groups commands by
  module, so the package restores the historical order — this pins it), and
* the ``python -m mtgcli.cli`` packaging entry point works.
"""
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from mtgcli.cli import app

runner = CliRunner()

# The commands the CLI exposes, as the user types them (kebab-case). This is the
# public contract referenced by BUILDER.md / agents/*.md — keep it exhaustive.
EXPECTED_COMMANDS = [
    "status", "init-data", "card", "search", "search-tags", "suggest",
    "commander-analyze", "validate", "deck-write", "deck-fill-lands", "enrich",
    "export", "suggest-lands", "deck-check", "themes", "theme-info", "explore",
    "temp-clean", "final-build", "price", "cards", "cards-batch", "prices",
    "prices-batch", "budget", "category-counts", "combos", "deck-swap",
    "preflight", "similar", "complements", "deck-gaps", "analyze-card", "report",
    # v0.8.0 categorizers + Consistency-engine Fase 4 (deliberate pin 34 -> 39);
    # order = registration order (deck.py commands, then misc.py's note).
    "deck-power", "deck-add", "deck-annotate", "deck-view", "note",
]


def _registered_command_names():
    """Command names as Typer exposes them on the CLI (underscores -> hyphens)."""
    return [
        (c.name or c.callback.__name__).replace("_", "-")
        for c in app.registered_commands
    ]


def test_expected_command_set_is_registered():
    assert sorted(_registered_command_names()) == sorted(EXPECTED_COMMANDS)


def test_command_order_matches_original():
    # Typer lists commands in registration order; the package restores the exact
    # order the pre-split cli.py produced. Pin it so a future re-grouping that
    # would change `mtg --help` output is caught.
    assert _registered_command_names() == EXPECTED_COMMANDS


def test_top_level_help_exits_zero():
    res = runner.invoke(app, ["--help"])
    assert res.exit_code == 0
    assert "Local MTG Commander deckbuilding CLI" in res.output


@pytest.mark.parametrize("cmd", EXPECTED_COMMANDS)
def test_command_help_exits_zero(cmd):
    res = runner.invoke(app, [cmd, "--help"])
    assert res.exit_code == 0, res.output


def test_module_entrypoint_help_via_subprocess():
    """`python -m mtgcli.cli --help` must work (packaging / __main__.py path)."""
    proc = subprocess.run(
        [sys.executable, "-m", "mtgcli.cli", "--help"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "commander-analyze" in proc.stdout
