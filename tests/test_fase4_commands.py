"""Regression: Consistency-engine Fase 4 CLI (deck-add, deck-annotate, survival fix).

- deck-add: THE drafting primitive — creates the annotated deck, batch+atomic,
  running budget total, config-in-deck.
- deck-annotate: --auto census seed (merge-only), --cards refinement, --sync-notes.
- deck-swap top-level-keys survival: rebuilding {commander, main_deck} dropped
  combos/agent_note/config (caught by the Fase-4 survival test; now preserved).
- deck-power consumes the consistency tier when the deck is annotated.
"""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mtgcli.cli import app
from mtgcli.config import SQLITE_PATH

runner = CliRunner()

needs_db = pytest.mark.skipif(
    not Path(str(SQLITE_PATH)).exists(), reason="card DB not built"
)


# The answered build contract (BUILDER §5 gate): deck-add's FIRST call refuses
# to create a deck without budget + bracket in --set-config.
_CONTRACT = ("--set-config", "budget=150", "--set-config", "bracket=n/a")


def _add(deck, cards, purpose, extra=()):
    return runner.invoke(app, ["deck-add", "--deck", str(deck), "--cards", cards,
                               "--purpose", purpose, *extra])


@needs_db
def test_deck_add_creates_validates_and_tracks_budget(tmp_path):
    deck = tmp_path / "d.json"
    r = _add(deck, "Sol Ring;Boros Signet", "ramp",
             ("--commander", "Ragost, Deft Gastronaut",
              "--set-config", "budget=150", "--set-config", "bracket=n/a"))
    assert r.exit_code == 0, r.output
    assert "running total" in r.output and "% of $150" in r.output
    data = json.loads(deck.read_text())
    assert data["commander"] == "Ragost, Deft Gastronaut"
    assert data["config"]["budget"] == "150"
    sol = next(e for e in data["main_deck"] if e["name"] == "Sol Ring")
    assert sol["purpose"] == ["RAMP"]


@needs_db
def test_deck_add_first_use_requires_build_contract(tmp_path):
    deck = tmp_path / "new.json"
    r = runner.invoke(app, ["deck-add", "--deck", str(deck), "--cards", "Sol Ring",
                            "--purpose", "ramp", "--commander",
                            "Ragost, Deft Gastronaut", "--json-output"])
    assert r.exit_code != 0
    err = json.loads(r.output)["error"]
    assert err["type"] == "validation"
    assert "budget" in err["message"] and "bracket" in err["message"]
    assert "BUILDER.md" in err["message"]          # points the agent at §5
    assert not deck.exists()                       # nothing was created
    # partial contract (budget only) is still not an answered contract
    r2 = _add(deck, "Sol Ring", "ramp", ("--commander", "Ragost, Deft Gastronaut",
                                         "--set-config", "budget=150"))
    assert r2.exit_code != 0 and not deck.exists()
    # explicit n/a answers ARE a contract ("No budget" is an answer, not a default)
    r3 = _add(deck, "Sol Ring", "ramp", ("--commander", "Ragost, Deft Gastronaut",
                                         "--set-config", "budget=n/a",
                                         "--set-config", "bracket=n/a"))
    assert r3.exit_code == 0, r3.output


@needs_db
def test_deck_add_contract_not_required_after_first_use(tmp_path):
    deck = tmp_path / "d.json"
    r = _add(deck, "Sol Ring", "ramp",
             ("--commander", "Ragost, Deft Gastronaut", *_CONTRACT))
    assert r.exit_code == 0, r.output
    r2 = _add(deck, "Boros Signet", "ramp")        # no contract flags needed now
    assert r2.exit_code == 0, r2.output


@needs_db
def test_deck_add_atomic_on_bad_name_and_color(tmp_path):
    deck = tmp_path / "d.json"
    _add(deck, "Sol Ring", "ramp", ("--commander", "Ragost, Deft Gastronaut",
                                    *_CONTRACT))
    r = runner.invoke(app, ["deck-add", "--deck", str(deck), "--cards",
                            "Krenkooo;Path to Exile", "--purpose", "removal",
                            "--json-output"])
    assert r.exit_code != 0
    assert json.loads(r.output)["error"]["type"] == "validation"
    r2 = _add(deck, "Rhystic Study", "draw")
    assert r2.exit_code != 0  # U outside RW
    data = json.loads(deck.read_text())
    assert len(data["main_deck"]) == 1  # nothing leaked in


@needs_db
def test_deck_add_first_use_requires_commander(tmp_path):
    r = _add(tmp_path / "new.json", "Sol Ring", "ramp")
    assert r.exit_code != 0


@needs_db
def test_deck_annotate_auto_and_refine_merge_only(tmp_path):
    deck = tmp_path / "d.json"
    _add(deck, "Sol Ring;Swords to Plowshares", "flex",
         ("--commander", "Ragost, Deft Gastronaut", *_CONTRACT))
    r = runner.invoke(app, ["deck-annotate", "--deck", str(deck), "--auto"])
    assert r.exit_code == 0, r.output
    data = json.loads(deck.read_text())
    sol = next(e for e in data["main_deck"] if e["name"] == "Sol Ring")
    swords = next(e for e in data["main_deck"] if e["name"] == "Swords to Plowshares")
    assert "FLEX" in sol["purpose"] and "RAMP" in sol["purpose"]  # merge, never remove
    assert "REMOVAL" in swords["purpose"]
    r2 = runner.invoke(app, ["deck-annotate", "--deck", str(deck),
                             "--cards", "Sol Ring", "--purpose-add", "synergy",
                             "--note", "es Food"])
    assert r2.exit_code == 0
    sol2 = next(e for e in json.loads(deck.read_text())["main_deck"]
                if e["name"] == "Sol Ring")
    assert "SYNERGY" in sol2["purpose"] and sol2["agent_note"] == "es Food"


@needs_db
def test_deck_annotate_unknown_card_rejects(tmp_path):
    deck = tmp_path / "d.json"
    _add(deck, "Sol Ring", "ramp", ("--commander", "Ragost, Deft Gastronaut",
                                    *_CONTRACT))
    r = runner.invoke(app, ["deck-annotate", "--deck", str(deck),
                            "--cards", "Ghost", "--purpose-add", "draw",
                            "--json-output"])
    assert r.exit_code != 0
    assert json.loads(r.output)["error"]["type"] == "validation"


@needs_db
def test_deck_swap_preserves_top_level_keys(tmp_path):
    deck = tmp_path / "d.json"
    deck.write_text(json.dumps({
        "commander": "Ragost, Deft Gastronaut",
        "agent_note": "food cannon", "config": {"budget": "150"},
        "combos": {"infinite": [], "non_infinite": [
            {"cards_needed": ["Heliod, Sun-Crowned", "Ragost, Deft Gastronaut"],
             "how_to": "untap"}], "utility": [], "auto_win": []},
        "main_deck": [{"name": "Swords to Plowshares", "quantity": 1,
                       "purpose": ["REMOVAL"]}],
    }))
    r = runner.invoke(app, ["deck-swap", "--deck", str(deck), "--commander",
                            "Ragost, Deft Gastronaut", "--swap",
                            "Swords to Plowshares=Path to Exile"])
    assert r.exit_code == 0, r.output
    data = json.loads(deck.read_text())
    assert data["agent_note"] == "food cannon"          # survived (was dropped before)
    assert data["config"] == {"budget": "150"}
    assert data["combos"]["non_infinite"]
    assert data["main_deck"][0]["name"] == "Path to Exile"
    assert data["main_deck"][0]["purpose"] == ["REMOVAL"]  # entry keys survive too


@needs_db
def test_deck_power_uses_consistency_tier_when_annotated(tmp_path):
    deck = tmp_path / "d.json"
    _add(deck, "Fiery Emancipation;Aetherflux Reservoir", "wincon",
         ("--commander", "Ragost, Deft Gastronaut", *_CONTRACT))
    _add(deck, "Sol Ring;Boros Signet", "ramp")
    _add(deck, "12 Mountain", "flex")
    r = runner.invoke(app, ["deck-power", "--deck", str(deck), "--commander",
                            "Ragost, Deft Gastronaut", "--json-output"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    ct = data["consistency_tier"]
    assert ct and ct["tier"] is not None and ct["band"]
    assert ct["components"]["wincon_access"]["routes"]


@needs_db
def test_deck_view_shows_metrics_and_card(tmp_path):
    deck = tmp_path / "d.json"
    _add(deck, "Sol Ring", "ramp", ("--commander", "Ragost, Deft Gastronaut",
                                    "--set-config", "budget=100",
                                    "--set-config", "bracket=n/a"))
    r = runner.invoke(app, ["deck-view", "--deck", str(deck)])
    assert r.exit_code == 0, r.output
    assert "by purpose" in r.output and "curve:" in r.output and "% of $100" in r.output
    assert "cost by type:" in r.output and "artifact=$" in r.output
    rj = runner.invoke(app, ["deck-view", "--deck", str(deck), "--json-output"])
    data = json.loads(rj.output)
    assert data["metrics"]["by_purpose"] == {"RAMP": 1}
    assert list(data["metrics"]["price_by_type"]) == ["artifact"]  # Sol Ring only
    rc = runner.invoke(app, ["deck-view", "--deck", str(deck), "--card", "Sol Ring"])
    assert rc.exit_code == 0 and "Add {C}{C}" in rc.output
    rmiss = runner.invoke(app, ["deck-view", "--deck", str(deck), "--card", "Ghost",
                                "--json-output"])
    assert rmiss.exit_code != 0
    assert json.loads(rmiss.output)["error"]["type"] == "validation"


@needs_db
def test_final_build_ships_deck_list_json(tmp_path, monkeypatch):
    import mtgcli.cli.commands.misc as misc_cmd
    monkeypatch.setattr(misc_cmd, "FINAL_BUILDS_DIR", tmp_path / "final-builds")
    deck = tmp_path / "d.json"
    _add(deck, "Sol Ring", "ramp", ("--commander", "Ragost, Deft Gastronaut",
                                    *_CONTRACT))
    _add(deck, "98 Mountain", "flex")
    expl = tmp_path / "e.md"
    expl.write_text("guide")
    r = runner.invoke(app, ["final-build", "--deck", str(deck), "--commander",
                            "Ragost, Deft Gastronaut", "--theme", "T", "--bracket",
                            "T3", "--explanation", str(expl), "--json-output"])
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    dj = Path(out["deck_json_path"])
    assert dj.name == "deck_list.json" and dj.exists()
    shipped = json.loads(dj.read_text())
    sol = next(e for e in shipped["main_deck"] if e["name"] == "Sol Ring")
    assert sol["purpose"] == ["RAMP"]          # the judgment travels
    assert shipped["config"]["budget"] == "150"
