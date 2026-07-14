"""Regression: v0.8.x backlog fixes (test build #4 / Kiki retro).

1a. `deck-remove` — deck-add's inverse: atomic batch, basics decrement,
    nonbasics drop whole, DFC front-face names resolve, running total printed.
1b. deck-swap OUT side matches DFC front-face names (the deck stores the
    DB-canonical "Front // Back"; the agent naturally types the front face).
2.  LEGENDARY_MATTERS ignores negated "nonlegendary" forms (Kiki-Jiki read
    "Legendary Matters high" from "target nonlegendary" — 9 FPs measured,
    all nonlegendary-copy effects; 142 true payoffs kept).
3.  BUILDER §5 gate on the legacy path: `deck-write` creating a NEW structured
    deck requires the answered build contract via --set-config, like deck-add.
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

_CONTRACT = ("--set-config", "budget=150", "--set-config", "bracket=n/a")


def _make_deck(deck, cards="Sol Ring;Boros Signet", purpose="ramp"):
    r = runner.invoke(app, ["deck-add", "--deck", str(deck), "--cards", cards,
                            "--purpose", purpose,
                            "--commander", "Ragost, Deft Gastronaut", *_CONTRACT])
    assert r.exit_code == 0, r.output
    return r


# ── 1a. deck-remove ────────────────────────────────────────────────────────────

@needs_db
def test_deck_remove_nonbasic_drops_whole_and_prints_running_total(tmp_path):
    deck = tmp_path / "d.json"
    _make_deck(deck)
    r = runner.invoke(app, ["deck-remove", "--deck", str(deck), "--cards", "Sol Ring"])
    assert r.exit_code == 0, r.output
    assert "running total" in r.output
    names = [e["name"] for e in json.loads(deck.read_text())["main_deck"]]
    assert "Sol Ring" not in names and "Boros Signet" in names


@needs_db
def test_deck_remove_basics_decrement_by_quantity(tmp_path):
    deck = tmp_path / "d.json"
    _make_deck(deck)
    r = runner.invoke(app, ["deck-add", "--deck", str(deck),
                            "--cards", "3 Mountain", "--purpose", "flex"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["deck-remove", "--deck", str(deck),
                            "--cards", "2 Mountain", "--json-output"])
    assert r.exit_code == 0, r.output
    mountain = next(e for e in json.loads(deck.read_text())["main_deck"]
                    if e["name"] == "Mountain")
    assert mountain.get("quantity", 1) == 1


@needs_db
def test_deck_remove_atomic_on_unknown_name(tmp_path):
    deck = tmp_path / "d.json"
    _make_deck(deck)
    r = runner.invoke(app, ["deck-remove", "--deck", str(deck),
                            "--cards", "Sol Ring;Not In This Deck", "--json-output"])
    assert r.exit_code != 0
    err = json.loads(r.output)
    assert err["error"]["type"] == "validation"
    # nothing removed — Sol Ring survives
    names = [e["name"] for e in json.loads(deck.read_text())["main_deck"]]
    assert "Sol Ring" in names


@needs_db
def test_deck_remove_resolves_dfc_front_face(tmp_path):
    deck = tmp_path / "d.json"
    _make_deck(deck, cards="Valakut Awakening", purpose="flex")
    stored = [e["name"] for e in json.loads(deck.read_text())["main_deck"]]
    canonical = next(n for n in stored if n.lower().startswith("valakut awakening"))
    r = runner.invoke(app, ["deck-remove", "--deck", str(deck),
                            "--cards", "Valakut Awakening", "--json-output"])
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["removed"][0]["name"] == canonical
    names = [e["name"] for e in json.loads(deck.read_text())["main_deck"]]
    assert canonical not in names


# ── 1b. deck-swap OUT side matches DFC front faces ─────────────────────────────

@needs_db
def test_deck_swap_out_matches_dfc_front_face(tmp_path):
    deck = tmp_path / "deck.json"
    deck.write_text(json.dumps({
        "commander": "Ragost, Deft Gastronaut",
        "main_deck": [
            {"name": "Valakut Awakening // Valakut Stoneforge", "quantity": 1},
            {"name": "Sol Ring", "quantity": 1},
        ],
    }))
    r = runner.invoke(app, ["deck-swap", "--deck", str(deck),
                            "--commander", "Ragost, Deft Gastronaut",
                            "--swap", "Valakut Awakening=Boros Signet",
                            "--json-output"])
    assert r.exit_code == 0, r.output
    names = [e["name"] for e in json.loads(deck.read_text())["main_deck"]]
    assert "Boros Signet" in names
    assert not any(n.startswith("Valakut Awakening") for n in names)


# ── 2. LEGENDARY_MATTERS negation guard ────────────────────────────────────────

def _profile(oracle):
    from mtgcli.analyzer.content import detect_keywords
    from mtgcli.analyzer.model import CardProfile
    p = CardProfile(name="t")
    detect_keywords(oracle, p)
    return p


def test_nonlegendary_restriction_is_not_legendary_matters():
    # Kiki-Jiki's actual clause shape — the test build #4 false-high
    p = _profile("{T}: Create a token that's a copy of target nonlegendary "
                 "creature you control, except it has haste.")
    assert not p.has_signal("LEGENDARY_MATTERS")


def test_true_legendary_payoff_still_reads():
    p = _profile("Legendary creatures you control get +1/+1 and have vigilance.")
    assert p.has_signal("LEGENDARY_MATTERS")


@needs_db
def test_kiki_and_shanid_read_correctly_from_db():
    from mtgcli.analyzer.analyze import analyze_card
    from mtgcli.cards.repository import CardRepository
    repo = CardRepository(str(SQLITE_PATH))
    kiki = analyze_card(repo.get_card_by_exact_name("Kiki-Jiki, Mirror Breaker"))
    assert not any(a["archetype"] == "Legendary Matters"
                   for a in kiki["archetype_support"])
    shanid = analyze_card(repo.get_card_by_exact_name("Shanid, Sleepers' Scourge"))
    bands = {a["archetype"]: a["band"] for a in shanid["archetype_support"]}
    assert bands.get("Legendary Matters") == "high"


# ── 3. deck-write §5 contract gate (legacy path) ───────────────────────────────

@needs_db
def test_deck_write_new_structured_deck_requires_contract(tmp_path):
    txt = tmp_path / "list.txt"
    txt.write_text("1 Sol Ring\n")
    out = tmp_path / "deck.json"
    r = runner.invoke(app, ["deck-write", "--input", str(txt), "--output", str(out),
                            "--commander", "Ragost, Deft Gastronaut", "--json-output"])
    assert r.exit_code != 0
    err = json.loads(r.output)
    assert err["error"]["type"] == "validation"
    assert "§5" in err["error"]["message"] or "core questions" in err["error"]["message"]
    assert not out.exists()


@needs_db
def test_deck_write_with_contract_stores_config(tmp_path):
    txt = tmp_path / "list.txt"
    txt.write_text("1 Sol Ring\n")
    out = tmp_path / "deck.json"
    r = runner.invoke(app, ["deck-write", "--input", str(txt), "--output", str(out),
                            "--commander", "Ragost, Deft Gastronaut",
                            "--set-config", "budget=n/a", "--set-config", "bracket=n/a",
                            "--json-output"])
    assert r.exit_code == 0, r.output
    data = json.loads(out.read_text())
    assert data["config"] == {"budget": "n/a", "bracket": "n/a"}


@needs_db
def test_deck_write_overwrite_of_existing_deck_is_exempt(tmp_path):
    # --force over an existing deck is a mid-flow rewrite, not a new draft
    txt = tmp_path / "list.txt"
    txt.write_text("1 Sol Ring\n")
    out = tmp_path / "deck.json"
    out.write_text(json.dumps({"commander": "Ragost, Deft Gastronaut", "main_deck": []}))
    r = runner.invoke(app, ["deck-write", "--input", str(txt), "--output", str(out),
                            "--commander", "Ragost, Deft Gastronaut", "--force",
                            "--json-output"])
    assert r.exit_code == 0, r.output


@needs_db
def test_deck_write_unstructured_conversion_is_exempt(tmp_path):
    # no commander -> plain format conversion, not a draft
    txt = tmp_path / "list.txt"
    txt.write_text("1 Sol Ring\n")
    out = tmp_path / "deck.json"
    r = runner.invoke(app, ["deck-write", "--input", str(txt), "--output", str(out),
                            "--json-output"])
    assert r.exit_code == 0, r.output
