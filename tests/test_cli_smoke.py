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
    "status", "init-data", "update-data", "card", "search", "search-tags", "suggest",
    "commander-analyze", "validate", "deck-write", "deck-fill-lands", "enrich",
    "export", "export-tcgplayer", "suggest-lands", "deck-check", "themes", "theme-info",
    "temp-clean", "final-build", "price", "cards", "cards-batch", "prices",
    "prices-batch", "budget", "category-counts", "deck-swap",
    "preflight", "similar", "complements", "deck-gaps", "analyze-card", "report",
    # v0.8.0 categorizers + Consistency-engine Fase 4 (deliberate pin 34 -> 39);
    # order = registration order (deck.py commands, then misc.py's note).
    # v0.8.0 REMOVED explore + combos (external EDHREC-style fetches — permission
    # liability; web research is the agent's job, recorded via `mtg note`): 39 -> 37.
    # v0.8.0 user-bulk collection (owned cards cost the budget $0): + bulk-add -> 38.
    # RANK power-meter (FUEL-SPINE): + deck-rank -> 39.
    # v0.8.x backlog: + deck-remove (deck-add's inverse, test build #4 friction) -> 41
    # (update-data was the 40th).
    "bulk-add", "deck-power", "deck-add", "deck-remove", "deck-annotate", "deck-view",
    "deck-rank", "note",
    # v0.9.0 localhost GUI: + gui -> 42.
    "gui",
    # v0.9.0 TCGplayer Mass Entry export (one-click buy URL): + export-tcgplayer -> 43
    # (registered right after export in _COMMAND_ORDER, listed above).
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


def test_update_data_deletes_and_rebuilds(tmp_path, monkeypatch):
    """update-data wipes raw+processed (keeping .gitkeep) then re-downloads/rebuilds.
    Network + build are mocked — this pins the delete/rebuild wiring, not the download."""
    import json
    import mtgcli.config as cfg
    import mtgcli.cli.commands.data as datacmd
    raw, proc = tmp_path / "raw", tmp_path / "processed"
    raw.mkdir(); proc.mkdir()
    (raw / ".gitkeep").write_text(""); (proc / ".gitkeep").write_text("")
    (raw / "scryfall_cards.json").write_text("OLD bulk")
    (proc / "mtg.sqlite").write_text("OLD db")
    monkeypatch.setattr(cfg, "RAW_DATA_DIR", raw)
    monkeypatch.setattr(cfg, "PROCESSED_DATA_DIR", proc)
    calls = {"dl": 0, "build": 0}

    def fake_dl():
        calls["dl"] += 1
        (raw / "scryfall_cards.json").write_text("NEW bulk")
        return raw / "scryfall_cards.json"

    def fake_build():
        calls["build"] += 1
        (proc / "mtg.sqlite").write_text("NEW db")
        return {"path": str(proc / "mtg.sqlite"), "unique_card_identities": 5,
                "cards_processed": 9, "cards_with_known_usd_price": 4,
                "cards_with_unknown_price": 1}

    monkeypatch.setattr(datacmd, "download_default_cards", fake_dl)
    monkeypatch.setattr(datacmd, "build_sqlite_database", fake_build)

    # destructive -> requires --yes (json mode errors instead of prompting)
    r0 = runner.invoke(app, ["update-data", "--json-output"])
    assert r0.exit_code == 1 and "confirmation_required" in r0.output
    assert calls == {"dl": 0, "build": 0}                 # nothing happened

    r = runner.invoke(app, ["update-data", "--yes", "--json-output"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert data["ok"] and data["downloaded"] and calls == {"dl": 1, "build": 1}
    assert any("scryfall_cards.json" in d for d in data["deleted"])
    assert any("mtg.sqlite" in d for d in data["deleted"])
    assert (raw / ".gitkeep").exists() and (proc / ".gitkeep").exists()   # .gitkeep preserved
    assert (raw / "scryfall_cards.json").read_text() == "NEW bulk"        # re-downloaded
