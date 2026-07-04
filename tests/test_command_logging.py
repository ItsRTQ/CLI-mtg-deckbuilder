"""Tests for the --log audit trail and the report command."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mtgcli.cli import app
from mtgcli import logging_util
from mtgcli.logging_util import append_log, _load_ongoing, _coerce_response, ONGOING_PATH
from mtgcli.config import LOGS_DIR

runner = CliRunner()


@pytest.fixture(autouse=True)
def clean_ongoing():
    if ONGOING_PATH.exists():
        ONGOING_PATH.unlink()
    yield
    if ONGOING_PATH.exists():
        ONGOING_PATH.unlink()


def test_append_log_assigns_global_seq():
    s1 = append_log("search", "mtg search --log", "text out", 0)
    s2 = append_log("analyze-card", "mtg analyze-card X --log", '{"a":1}', 0)
    assert (s1, s2) == (1, 2)
    log = _load_ongoing()
    assert log[0]["command"] == "search" and log[0]["response"] == "text out"
    assert log[1]["response"] == {"a": 1}          # JSON output parsed
    assert all("timestamp" in e and "exit_code" in e for e in log)


def test_coerce_response_json_vs_text():
    assert _coerce_response('{"k": 2}') == {"k": 2}
    assert _coerce_response('[1, 2]') == [1, 2]
    assert _coerce_response("Found 3 cards") == "Found 3 cards"


def test_report_consolidates_and_clears():
    append_log("search", "mtg search --log", "out", 0)
    res = runner.invoke(app, ["report", "--name", "test-report", "--note", "hello", "--json-output"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data["command_count"] == 1
    assert data["notes"] == ["hello"]
    assert not ONGOING_PATH.exists()               # cleared by default
    out = LOGS_DIR / "test-report.json"
    assert out.exists()
    out.unlink()


def test_report_keep_retains_ongoing():
    append_log("search", "mtg search --log", "out", 0)
    res = runner.invoke(app, ["report", "--name", "keep-report", "--keep"])
    assert res.exit_code == 0
    assert ONGOING_PATH.exists()                   # retained with --keep
    out = LOGS_DIR / "keep-report.json"
    if out.exists():
        out.unlink()


def test_report_empty_errors():
    res = runner.invoke(app, ["report", "--name", "empty"])
    assert res.exit_code == 1


def test_log_flag_end_to_end_via_main(tmp_path):
    # the --log flag is stripped by main() and the command still runs + gets logged
    from mtgcli.config import SQLITE_PATH
    if not SQLITE_PATH.exists():
        pytest.skip("DB not built")
    proc = subprocess.run([sys.executable, "-m", "mtgcli.cli", "search-tags", "evasion",
                           "--limit", "1", "--json-output", "--log"],
                          capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    # note: -m runs the module; main() guard handles --log
    log = _load_ongoing()
    assert any(e["command"] == "search-tags" for e in log)


# ── report --summary: derived calibration metrics ─────────────────────────────

def test_summarize_log_metrics():
    from mtgcli.logging_util import summarize_log
    entries = [
        {"seq": 1, "command": "search-tags", "full_command": "mtg search-tags evasion --log", "exit_code": 0},
        {"seq": 2, "command": "analyze-card", "full_command": 'mtg analyze-card "Toxrill, the Corrosive" --log', "exit_code": 0},
        {"seq": 3, "command": "analyze-card", "full_command": "mtg analyze-card Gargos --log", "exit_code": 0},
        {"seq": 4, "command": "analyze-card", "full_command": "mtg analyze-card Nope --log", "exit_code": 1},
    ]
    s = summarize_log(entries)
    assert s["total_commands"] == 4
    assert s["command_counts"]["analyze-card"] == 3
    assert s["analyze_card_count"] == 3
    assert "Toxrill, the Corrosive" in s["analyze_card_calls"]   # quoted arg preserved
    assert "Gargos" in s["analyze_card_calls"]
    assert s["failure_count"] == 1 and s["failures"][0]["seq"] == 4


def test_first_arg_quoting():
    from mtgcli.logging_util import _first_arg
    assert _first_arg('"Toxrill, the Corrosive" --json-output') == "Toxrill, the Corrosive"
    assert _first_arg("Gargos --log") == "Gargos"
    assert _first_arg("--json-output") == ""


def test_report_summary_embedded_and_printed():
    append_log("analyze-card", 'mtg analyze-card "X" --log', "out", 0)
    append_log("search", "mtg search --log", "out", 1)
    res = runner.invoke(app, ["report", "--name", "sum-report", "--summary", "--json-output"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert "summary" in data
    assert data["summary"]["failure_count"] == 1
    out = LOGS_DIR / "sum-report.json"
    if out.exists():
        out.unlink()
