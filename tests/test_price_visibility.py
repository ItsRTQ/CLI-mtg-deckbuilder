"""Regression: price visibility at pick time (full build #3 friction, v0.8.0 polishing).

Two features:
1. Search-family human output shows a price chip per result row (``fmt_price``) — the
   shortlists filtered by --max-price but never SHOWED the price, so hand allocation
   ran on memory prices (Flawless Maneuver remembered ~$4, actual $20.30).
2. ``prices-batch`` accepts repeatable ``--name`` (no file needed) so hand-picked
   candidates can be costed BEFORE they join a list, with a known-price total.
   JSON stays a plain list in file mode (backward compat); --name mode returns an
   object with ``known_total``.
"""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mtgcli.cli import app
from mtgcli.cli._shared import fmt_price
from mtgcli.config import SQLITE_PATH

runner = CliRunner()

needs_db = pytest.mark.skipif(
    not Path(str(SQLITE_PATH)).exists(), reason="card DB not built"
)


# ---------- fmt_price unit behavior ----------

def test_fmt_price_known():
    assert fmt_price({"usd_price": 1.234}) == " [green]$1.23[/green]"
    assert fmt_price({"usd_price": "20.3"}) == " [green]$20.30[/green]"


def test_fmt_price_unknown():
    assert fmt_price({"usd_price": None}) == " [dim]$?[/dim]"
    assert fmt_price({}) == " [dim]$?[/dim]"


# ---------- search family shows the chip ----------

@needs_db
def test_search_tags_row_shows_price():
    result = runner.invoke(app, ["search-tags", "lifegain_payoff", "--colors", "W",
                                 "--limit", "3"])
    assert result.exit_code == 0
    # every result row carries a price chip ($X.XX or $?)
    rows = [l for l in result.output.splitlines() if l.strip().startswith("- ")]
    assert rows, result.output
    assert all("$" in r for r in rows), result.output


@needs_db
def test_search_row_shows_price():
    result = runner.invoke(app, ["search", "--oracle", "devotion to", "--limit", "3"])
    assert result.exit_code == 0
    rows = [l for l in result.output.splitlines() if l.strip().startswith("- ")]
    assert rows, result.output
    assert all("$" in r for r in rows), result.output


# ---------- prices-batch --name mode ----------

@needs_db
def test_prices_batch_names_json_object_with_total():
    result = runner.invoke(app, ["prices-batch", "--name", "Sol Ring",
                                 "--name", "Arcane Signet", "--json-output"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, dict)
    assert {"results", "known_total", "unknown_count", "not_found_count"} <= set(data)
    assert len(data["results"]) == 2
    assert data["known_total"] > 0
    assert data["not_found_count"] == 0


@needs_db
def test_prices_batch_names_human_total_and_suggestions():
    result = runner.invoke(app, ["prices-batch", "--name", "Sol Ring",
                                 "--name", "Krenkooo"])
    assert result.exit_code == 0, result.output
    assert "Known-price total: $" in result.output
    assert "not found" in result.output
    # the ad-hoc-name path offers fuzzy suggestions like `card` does
    assert "did you mean" in result.output


@needs_db
def test_prices_batch_file_mode_json_stays_list(tmp_path):
    deck = tmp_path / "list.txt"
    deck.write_text("1 Sol Ring\n1 Arcane Signet\n", encoding="utf-8")
    result = runner.invoke(app, ["prices-batch", str(deck), "--json-output"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, list)  # backward-compatible shape
    assert len(data) == 2


def test_prices_batch_no_input_validation_error():
    result = runner.invoke(app, ["prices-batch", "--json-output"])
    assert result.exit_code != 0
    data = json.loads(result.output)
    assert data["error"]["type"] == "validation"
