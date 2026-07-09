"""Regression: the edhrec_rank popularity signal (v0.8.0 tentativo items).

1. `deck-check` gains an INFORMATIONAL `staple_density` block — consider-only,
   deliberately never a warning and never gating (popularity != power; synergy-dense
   decks read low by design). Thresholds calibrated on the 4 real agent builds
   (43-73% band; <40% is an outlier flag).
2. `--max-rank` on search/search-tags filters candidates by popularity, keeps
   unknown-rank cards, and OVERSAMPLES before post-filtering so it never starves the
   result list (first live check: --max-rank 500 on a limit-5 fetch returned nothing).
"""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mtgcli.cli import app
from mtgcli.cli._shared import _apply_max_rank
from mtgcli.config import SQLITE_PATH
from mtgcli.deckbuilder.deck_check import staple_density

runner = CliRunner()

needs_db = pytest.mark.skipif(
    not Path(str(SQLITE_PATH)).exists(), reason="card DB not built"
)


def _card(name, rank, type_line="Artifact", qty=1):
    return {"name": name, "edhrec_rank": rank, "type_line": type_line, "quantity": qty}


# ---------- staple_density unit behavior ----------

def test_density_median_pct_and_lands_excluded():
    cards = [
        _card("A", 100), _card("B", 1500), _card("C", 9000),
        _card("Command Tower", 2, type_line="Land"),  # lands never count
    ]
    d = staple_density(cards)
    assert d["ranked_nonland_count"] == 3
    assert d["median_rank"] == 1500
    assert d["pct_top_2000"] == round(100 * 2 / 3, 1)


def test_density_labels_calibrated_bands():
    dense = staple_density([_card(str(i), 100) for i in range(10)])
    assert dense["read"] == "staple-dense"
    mixed = staple_density([_card(str(i), 100) for i in range(5)]
                           + [_card(f"n{i}", 9000) for i in range(5)])
    assert mixed["read"] == "mixed"
    niche = staple_density([_card(str(i), 9000) for i in range(9)] + [_card("s", 100)])
    assert niche["read"].startswith("niche/synergy-dense")


def test_density_consider_only_note_and_none_when_unranked():
    d = staple_density([_card("A", 100)])
    assert "consider-only" in d["note"] and "NOT a power verdict" in d["note"]
    assert staple_density([_card("A", None)]) is None
    assert staple_density([]) is None


def test_density_counts_unranked_separately():
    d = staple_density([_card("A", 100), _card("B", None)])
    assert d["unranked_nonland_count"] == 1


def test_density_is_never_a_warning():
    # the signal must not leak into warnings (consider-only contract)
    from mtgcli.deckbuilder.deck_check import check_deck_quality
    report = check_deck_quality([_card(str(i), 9000) for i in range(40)]
                                + [_card(f"L{i}", 1, type_line="Basic Land") for i in range(36)])
    assert "staple_density" in report
    assert not any("staple" in w.lower() or "rank" in w.lower() for w in report["warnings"])


# ---------- _apply_max_rank ----------

def test_max_rank_filters_and_keeps_unknown():
    results = [_card("A", 100), _card("B", 5000), _card("C", None)]
    out = _apply_max_rank(results, 500)
    assert [c["name"] for c in out] == ["A", "C"]
    assert _apply_max_rank(results, None) == results


# ---------- CLI integration (DB-backed) ----------

@needs_db
def test_search_tags_max_rank_does_not_starve():
    # the starvation regression: a tight rank cap on a small limit must still return staples
    result = runner.invoke(app, ["search-tags", "ramp", "--max-rank", "500", "--limit", "5"])
    assert result.exit_code == 0
    rows = [l for l in result.output.splitlines() if l.strip().startswith("- ")]
    assert rows, result.output


@needs_db
def test_deck_check_json_carries_staple_density(tmp_path):
    deck = tmp_path / "deck.json"
    deck.write_text(json.dumps({"commander": "Krenko, Mob Boss",
                                "main_deck": [{"name": "Sol Ring", "quantity": 1},
                                              {"name": "Arcane Signet", "quantity": 1}]}),
                    encoding="utf-8")
    result = runner.invoke(app, ["deck-check", "--commander", "Krenko, Mob Boss",
                                 "--deck", str(deck), "--json-output"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    sd = data.get("staple_density")
    assert sd and sd["ranked_nonland_count"] == 2 and "consider-only" in sd["note"]
