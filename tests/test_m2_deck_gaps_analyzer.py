"""M2 consumer #2: deck-gaps audits the deck against analyzer.archetype_support.

For every high/very_high band the analyzer reads on the commander, deck-gaps counts the
deck cards serving that plan (using the analyzer's OWN archetype vocabulary from
mapping._ARCHETYPE_RULES — no separate curation) and reports a plan_gap when thin.
"""
import json

import pytest
from typer.testing import CliRunner

from mtgcli.config import SQLITE_PATH
from mtgcli.cli import app

pytestmark = pytest.mark.skipif(not SQLITE_PATH.exists(), reason="card DB not built")

runner = CliRunner()

OFF_PLAN = "1 Sol Ring\n1 Arcane Signet\n1 Cultivate\n1 Lightning Bolt\n1 Mountain\n"
ON_PLAN = (
    "1 Goblin Rabblemaster\n1 Siege-Gang Commander\n1 Dragon Fodder\n"
    "1 Krenko's Command\n1 Hordeling Outburst\n1 Impact Tremors\n"
)


def _gaps(tmp_path, decklist):
    f = tmp_path / "deck.txt"
    f.write_text(decklist)
    res = runner.invoke(app, ["deck-gaps", "--deck", str(f), "--commander", "Krenko, Mob Boss",
                              "--archetype", "tokens", "--json-output"])
    assert res.exit_code == 0, res.stdout
    return json.loads(res.stdout)


def test_off_plan_deck_reports_plan_gap(tmp_path):
    d = _gaps(tmp_path, OFF_PLAN)
    assert any(s["archetype"] == "Go Wide" and s["band"] in ("high", "very_high")
               for s in d["analyzer_support"])
    gw = [g for g in d["plan_gaps"] if g["archetype"] == "Go Wide"]
    assert gw and gw[0]["have"] == 0
    assert gw[0]["fill_command"].startswith("mtg search-tags")


def test_on_plan_deck_has_no_go_wide_plan_gap(tmp_path):
    d = _gaps(tmp_path, ON_PLAN)
    assert not [g for g in d["plan_gaps"] if g["archetype"] == "Go Wide"]
