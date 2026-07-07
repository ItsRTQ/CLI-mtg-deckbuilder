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

def test_load_user_bulk_decklist_format(tmp_path):
    f = tmp_path / "collection.txt"
    f.write_text("# staples box\n2 Sol Ring\nArcane Signet\n3x Mountain\nSol Ring\n")
    owned = load_user_bulk(f)
    assert owned == {"Sol Ring": 3, "Arcane Signet": 1, "Mountain": 3}
    assert load_user_bulk(tmp_path / "missing.txt") == {}


def test_save_load_roundtrip_and_lookup(tmp_path):
    f = tmp_path / "collection.txt"
    save_user_bulk({"Sol Ring": 2, "Lightning Bolt": 1, "Gone": 0}, f)
    assert load_user_bulk(f) == {"Sol Ring": 2, "Lightning Bolt": 1}  # qty 0 dropped
    assert owned_lookup({"Sol Ring": 2}) == {"sol ring": 2}


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


def test_budget_summary_partial_ownership_bills_the_rest():
    entries = [{"name": "Shock", "quantity": 4, "usd_price": 0.5}]
    s = build_budget_summary(entries, owned={"shock": 1})
    assert s["known_price_total"] == 1.5          # 3 billed of 4
    line = s["breakdown"][0]
    assert line["quantity"] == 3 and line["owned_excluded"] == 1
    # no owned dict -> everything bills (backward compatible)
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
    assert data["collection_size"] == 3 and data["unique_names"] == 2

    r3 = runner.invoke(app, ["bulk-add", "--remove", "Sol Ring", "--json-output"])
    assert json.loads(r3.output)["collection_size"] == 2
    assert load_user_bulk(tmp_path / "collection.txt")["Sol Ring"] == 1


@needs_db
def test_budget_command_applies_and_disables_bulk(tmp_path, monkeypatch):
    import mtgcli.deckbuilder.user_bulk as ub
    monkeypatch.setattr(ub, "USER_BULK_FILE", tmp_path / "collection.txt")
    (tmp_path / "collection.txt").write_text("1 Rhystic Study\n")
    deck = tmp_path / "deck.txt"
    deck.write_text("1 Rhystic Study\n1 Sol Ring\n")

    r = runner.invoke(app, ["budget", str(deck), "--json-output"])
    s = json.loads(r.output)
    assert s["owned_cards_count"] == 1 and s["owned_value_excluded"] > 0
    total_with_bulk = s["known_price_total"]

    r2 = runner.invoke(app, ["budget", str(deck), "--no-bulk", "--json-output"])
    s2 = json.loads(r2.output)
    assert s2["owned_cards_count"] == 0
    assert s2["known_price_total"] > total_with_bulk
