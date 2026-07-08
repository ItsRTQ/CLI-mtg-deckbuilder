"""Regression: the user-bulk collection (owned cards cost the budget $0).

- user_bulk loader/saver: decklist format, comments, quantity merge, roundtrip.
- build_budget_summary(owned=...): owned copies excluded up to owned qty,
  visible in owned_cards_count / owned_value_excluded / breakdown lines —
  never silently.
- bulk-add CLI: validated batch add/remove (atomic, fuzzy did-you-mean),
  --list, and budget --no-bulk restoring the full bill.
"""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mtgcli.cli import app
from mtgcli.config import SQLITE_PATH
from mtgcli.deckbuilder.pricing import build_budget_summary
from mtgcli.deckbuilder.user_bulk import load_user_bulk, owned_lookup, save_user_bulk

runner = CliRunner()

needs_db = pytest.mark.skipif(
    not Path(str(SQLITE_PATH)).exists(), reason="card DB not built"
)


# ---------- loader / saver ----------

def test_load_user_bulk_presence_not_quantity(tmp_path):
    f = tmp_path / "collection.txt"
    f.write_text("# staples box\n2 Sol Ring\nArcane Signet\n3x Mountain\nSol Ring\n")
    owned = load_user_bulk(f)
    # PRESENCE — the leading quantities are ignored; each owned name -> 1
    assert owned == {"Sol Ring": 1, "Arcane Signet": 1, "Mountain": 1}
    assert load_user_bulk(tmp_path / "missing.txt") == {}


def test_save_load_roundtrip_and_lookup_with_defaults(tmp_path):
    f = tmp_path / "collection.txt"
    save_user_bulk({"Sol Ring", "Lightning Bolt"}, f)   # names, no quantities
    assert load_user_bulk(f) == {"Sol Ring": 1, "Lightning Bolt": 1}
    # owned_lookup returns a lowercased SET and injects the DEFAULT_OWNED staples
    lk = owned_lookup({"Lightning Bolt"})
    assert "lightning bolt" in lk
    assert {"plains", "island", "swamp", "mountain", "forest", "sol ring",
            "arcane signet"} <= lk                       # defaults always assumed
    # defaults can be turned off
    assert owned_lookup(set(), include_defaults=False) == set()


# ---------- budget math ----------

def _entries():
    return [
        {"name": "Rhystic Study", "quantity": 1, "usd_price": 30.0},
        {"name": "Sol Ring", "quantity": 1, "usd_price": 1.0},
        {"name": "Mystery", "quantity": 1, "usd_price": None},
    ]


def test_budget_summary_excludes_owned_visibly():
    s = build_budget_summary(_entries(), owned={"rhystic study": 1, "mystery": 1})
    assert s["known_price_total"] == 1.0          # only Sol Ring bills
    assert s["owned_cards_count"] == 2
    assert s["owned_value_excluded"] == 30.0      # unknown price excludes at $0
    assert s["unknown_price_cards"] == []         # owned unknown doesn't poison confidence
    assert s["budget_confidence"] == "complete"
    names = [c["name"] for c in s["breakdown"]]
    assert "Rhystic Study" not in names           # fully owned -> not billed


def test_budget_summary_owned_frees_all_copies():
    # PRESENCE: an owned card is free for ALL its copies (no per-copy counting).
    entries = [{"name": "Shock", "quantity": 4, "usd_price": 0.5}]
    s = build_budget_summary(entries, owned={"shock"})
    assert s["known_price_total"] == 0.0          # owned -> all 4 free
    assert s["owned_cards_count"] == 4
    assert all(c["name"] != "Shock" for c in s["breakdown"])
    # no owned -> everything bills (backward compatible)
    assert build_budget_summary(entries)["known_price_total"] == 2.0


# ---------- CLI ----------

@needs_db
def test_bulk_add_validates_atomic_and_lists(tmp_path, monkeypatch):
    import mtgcli.deckbuilder.user_bulk as ub
    monkeypatch.setattr(ub, "USER_BULK_FILE", tmp_path / "collection.txt")
    r = runner.invoke(app, ["bulk-add", "--cards", "Sol Ring;Krenkooo",
                            "--json-output"])
    assert r.exit_code != 0
    err = json.loads(r.output)["error"]
    assert err["type"] == "validation" and "Krenko" in err["message"]  # fuzzy hint
    assert not (tmp_path / "collection.txt").exists()                  # atomic

    r2 = runner.invoke(app, ["bulk-add", "--cards", "2 Sol Ring;Arcane Signet",
                             "--json-output"])
    assert r2.exit_code == 0, r2.output
    data = json.loads(r2.output)
    # PRESENCE: "2 Sol Ring" records Sol Ring once -> 2 owned names, not 3 copies
    assert data["collection_size"] == 2 and data["unique_names"] == 2

    r3 = runner.invoke(app, ["bulk-add", "--remove", "Sol Ring", "--json-output"])
    assert json.loads(r3.output)["collection_size"] == 1
    assert "Sol Ring" not in load_user_bulk(tmp_path / "collection.txt")


@needs_db
def test_budget_command_applies_and_disables_bulk(tmp_path, monkeypatch):
    import mtgcli.deckbuilder.user_bulk as ub
    monkeypatch.setattr(ub, "USER_BULK_FILE", tmp_path / "collection.txt")
    (tmp_path / "collection.txt").write_text("1 Rhystic Study\n")
    deck = tmp_path / "deck.txt"
    deck.write_text("1 Rhystic Study\n1 Sol Ring\n")

    r = runner.invoke(app, ["budget", str(deck), "--json-output"])
    s = json.loads(r.output)
    # Rhystic (explicit) + Sol Ring (DEFAULT_OWNED) both excluded
    assert s["owned_cards_count"] == 2 and s["owned_value_excluded"] > 0
    total_with_bulk = s["known_price_total"]

    r2 = runner.invoke(app, ["budget", str(deck), "--no-bulk", "--json-output"])
    s2 = json.loads(r2.output)
    assert s2["owned_cards_count"] == 0
    assert s2["known_price_total"] > total_with_bulk


def test_save_writes_txt_and_json_and_json_fallback(tmp_path):
    from mtgcli.deckbuilder.user_bulk import _load_json
    txt = tmp_path / "collection.txt"
    jpath = tmp_path / "collection.json"
    save_user_bulk({"Sol Ring", "Mana Crypt"}, path=txt)
    # both files written
    assert txt.exists() and jpath.exists()
    # json is structured + agent-friendly: a names list (no quantities)
    data = json.loads(jpath.read_text())
    assert data["count"] == 2
    assert set(data["cards"]) == {"Sol Ring", "Mana Crypt"}
    # txt is canonical on load; json is a faithful fallback when txt is gone
    assert load_user_bulk(txt) == {"Sol Ring": 1, "Mana Crypt": 1}
    assert _load_json(jpath) == {"Sol Ring": 1, "Mana Crypt": 1}


@needs_db
def test_bulk_add_import_txt_and_json(tmp_path, monkeypatch):
    import mtgcli.deckbuilder.user_bulk as ub
    monkeypatch.setattr(ub, "USER_BULK_FILE", tmp_path / "collection.txt")
    # import a bought deck as .txt: not-found card is SKIPPED (not atomic), rest import
    lst = tmp_path / "bought.txt"
    lst.write_text("2 Sol Ring\n1 Arcane Signet\n1 Definitely Not A Real Card\n")
    r = runner.invoke(app, ["bulk-add", "--import", str(lst), "--json-output"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    # PRESENCE: Sol Ring + Arcane Signet owned (2 names); fake skipped
    assert data["collection_size"] == 2
    assert {s["name"] for s in data["imported_skipped"]} == {"Definitely Not A Real Card"}
    # import a deck .json: commander + main_deck both become owned
    dj = tmp_path / "deck.json"
    dj.write_text(json.dumps({"commander": "Sol Ring",
                              "main_deck": [{"name": "Command Tower", "quantity": 1}]}))
    runner.invoke(app, ["bulk-add", "--import", str(dj), "--json-output"])
    owned = load_user_bulk(tmp_path / "collection.txt")
    assert owned == {"Sol Ring": 1, "Arcane Signet": 1, "Command Tower": 1}  # commander counted, presence
