"""
Tests for the mtg combos command — fetcher, parser, and CLI integration.

All HTTP calls are mocked; no live web requests.
"""
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mtgcli.combos.fetcher import build_combo_url, fetch_combo_data
from mtgcli.combos.parser import filter_combos, parse_combos, USE_GUIDANCE
from mtgcli.explore.slug import commander_to_slug


# ─── Slug formatting ──────────────────────────────────────────────────────────

def test_slug_edgar_markov():
    assert commander_to_slug("Edgar Markov") == "edgar-markov"


def test_slug_atraxa():
    assert commander_to_slug("Atraxa, Praetors' Voice") == "atraxa-praetors-voice"


def test_slug_belakor():
    assert commander_to_slug("Be'lakor, the Dark Master") == "belakor-the-dark-master"


def test_slug_caesar():
    assert commander_to_slug("Caesar, Legion's Emperor") == "caesar-legions-emperor"


def test_slug_no_double_hyphens():
    result = commander_to_slug("Henzie  'Toolbox' Torre")
    assert "--" not in result


# ─── URL resolution ───────────────────────────────────────────────────────────

def test_url_template_with_slug_placeholder(monkeypatch):
    monkeypatch.setenv("COMBOURL", "https://example.com/combos/{slug}.json")
    with patch("mtgcli.combos.fetcher.load_dotenv"):
        url = build_combo_url("Edgar Markov")
    assert url == "https://example.com/combos/edgar-markov.json"


def test_url_base_appends_slug_json(monkeypatch):
    monkeypatch.setenv("COMBOURL", "https://example.com/combos/")
    with patch("mtgcli.combos.fetcher.load_dotenv"):
        url = build_combo_url("Edgar Markov")
    assert url == "https://example.com/combos/edgar-markov.json"


def test_url_base_without_trailing_slash(monkeypatch):
    monkeypatch.setenv("COMBOURL", "https://example.com/combos")
    with patch("mtgcli.combos.fetcher.load_dotenv"):
        url = build_combo_url("Edgar Markov")
    assert url == "https://example.com/combos/edgar-markov.json"


def test_missing_combourl_raises(monkeypatch):
    monkeypatch.delenv("COMBOURL", raising=False)
    with patch("mtgcli.combos.fetcher.load_dotenv"):
        with pytest.raises(ValueError, match="Configuration error"):
            build_combo_url("Edgar Markov")


# ─── HTTP fetch ───────────────────────────────────────────────────────────────

def _mock_response(status_code=200, json_data=None):
    mock = MagicMock()
    mock.status_code = status_code
    if json_data is not None:
        mock.json.return_value = json_data
    else:
        mock.json.side_effect = ValueError("bad json")
    return mock


def test_fetch_returns_parsed_json():
    payload = {"container": {"json_dict": {"cardlists": []}}}
    with patch("mtgcli.combos.fetcher.requests.get", return_value=_mock_response(200, payload)):
        result = fetch_combo_data("https://example.com/combos/edgar-markov.json")
    assert result == payload


def test_fetch_raises_on_non_200():
    with patch("mtgcli.combos.fetcher.requests.get", return_value=_mock_response(404)):
        with pytest.raises(ValueError, match="HTTP 404"):
            fetch_combo_data("https://example.com/combos/unknown.json")


def test_fetch_raises_on_invalid_json():
    with patch("mtgcli.combos.fetcher.requests.get", return_value=_mock_response(200, None)):
        with pytest.raises(ValueError, match="Invalid JSON"):
            fetch_combo_data("https://example.com/combos/edgar-markov.json")


def test_fetch_raises_on_timeout():
    import requests as _requests
    with patch(
        "mtgcli.combos.fetcher.requests.get",
        side_effect=_requests.exceptions.Timeout(),
    ):
        with pytest.raises(ValueError, match="Timeout"):
            fetch_combo_data("https://example.com/combos/edgar-markov.json")


def test_fetch_raises_on_connection_error():
    import requests as _requests
    with patch(
        "mtgcli.combos.fetcher.requests.get",
        side_effect=_requests.exceptions.ConnectionError("refused"),
    ):
        with pytest.raises(ValueError, match="Connection error"):
            fetch_combo_data("https://example.com/combos/edgar-markov.json")


# ─── Parser ───────────────────────────────────────────────────────────────────

_SAMPLE_RAW = {
    "container": {
        "json_dict": {
            "cardlists": [
                {
                    "cardviews": [
                        {"name": "Gravecrawler"},
                        {"name": "Phyrexian Altar"},
                    ],
                    "combo": {
                        "results": ["Infinite death triggers", "Infinite mana"],
                        "comboVote": {"bracket": "2"},
                    },
                },
                {
                    "cardviews": [
                        {"name": "Mikaeus, the Unhallowed"},
                        {"name": "Triskelion"},
                    ],
                    "combo": {
                        "results": ["Infinite damage"],
                        "comboVote": None,
                    },
                },
                {
                    "cardviews": [
                        {"name": "Bloodghast"},
                        {"name": "Skullclamp"},
                        {"name": "Zulaport Cutthroat"},
                    ],
                    "combo": {
                        "results": ["Infinite draw", "Drain all opponents"],
                        "comboVote": {"bracket": "3"},
                    },
                },
            ]
        }
    }
}


def test_parse_extracts_cards_and_results():
    combos = parse_combos(_SAMPLE_RAW)
    assert len(combos) == 3
    assert "Gravecrawler" in combos[0]["cards"]
    assert "Infinite death triggers" in combos[0]["results"]


def test_parse_bracket_from_combo_vote():
    combos = parse_combos(_SAMPLE_RAW)
    assert combos[0]["bracket"] == "2"
    assert combos[2]["bracket"] == "3"


def test_parse_bracket_none_combo_vote():
    combos = parse_combos(_SAMPLE_RAW)
    assert combos[1]["bracket"] == "N/A"


def test_parse_missing_combo_vote_key():
    raw = {
        "container": {
            "json_dict": {
                "cardlists": [
                    {
                        "cardviews": [{"name": "Card A"}, {"name": "Card B"}],
                        "combo": {"results": ["Infinite mana"]},
                    }
                ]
            }
        }
    }
    combos = parse_combos(raw)
    assert combos[0]["bracket"] == "N/A"


def test_parse_empty_cardlists():
    raw = {"container": {"json_dict": {"cardlists": []}}}
    assert parse_combos(raw) == []


def test_parse_empty_raw_data():
    assert parse_combos({}) == []


def test_parse_missing_container():
    assert parse_combos({"other": "data"}) == []


def test_parse_skips_entries_with_no_cards():
    raw = {
        "container": {
            "json_dict": {
                "cardlists": [
                    {"cardviews": [], "combo": {"results": [], "comboVote": None}},
                    {
                        "cardviews": [{"name": "Sol Ring"}],
                        "combo": {"results": ["Infinite mana"], "comboVote": {"bracket": "1"}},
                    },
                ]
            }
        }
    }
    combos = parse_combos(raw)
    assert len(combos) == 1
    assert combos[0]["cards"] == ["Sol Ring"]


# ─── Filters ─────────────────────────────────────────────────────────────────

def test_filter_by_exact_bracket():
    combos = parse_combos(_SAMPLE_RAW)
    result = filter_combos(combos, bracket="2")
    assert len(result) == 1
    assert result[0]["bracket"] == "2"


def test_filter_by_max_bracket():
    combos = parse_combos(_SAMPLE_RAW)
    result = filter_combos(combos, max_bracket="2")
    assert all(c["bracket"] in ("1", "2") for c in result)
    assert len(result) == 1  # only bracket "2" is numeric ≤ 2; "N/A" is excluded


def test_filter_by_limit():
    combos = parse_combos(_SAMPLE_RAW)
    result = filter_combos(combos, limit=1)
    assert len(result) == 1


def test_filter_no_filters_returns_all():
    combos = parse_combos(_SAMPLE_RAW)
    assert filter_combos(combos) == combos


# ─── Use guidance ─────────────────────────────────────────────────────────────

def test_use_guidance_not_mandatory():
    assert USE_GUIDANCE["mandatory_includes"] is False
    assert "optional" in USE_GUIDANCE["note"].lower() or "context" in USE_GUIDANCE["note"].lower()


# ─── CLI integration ──────────────────────────────────────────────────────────

def _make_cli_raw():
    return {
        "container": {
            "json_dict": {
                "cardlists": [
                    {
                        "cardviews": [{"name": "Card A"}, {"name": "Card B"}],
                        "combo": {
                            "results": ["Infinite damage"],
                            "comboVote": {"bracket": "2"},
                        },
                    }
                ]
            }
        }
    }


def test_cli_combos_json_output(tmp_path, monkeypatch):
    from typer.testing import CliRunner
    from mtgcli.cli import app

    monkeypatch.setenv("COMBOURL", "https://example.com/combos/")
    with patch("mtgcli.combos.fetcher.load_dotenv"), \
         patch("mtgcli.combos.fetcher.requests.get", return_value=_mock_response(200, _make_cli_raw())):
        runner = CliRunner()
        result = runner.invoke(app, [
            "combos",
            "--commander", "Edgar Markov",
            "--no-write",
            "--json-output",
        ])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["commander"] == "Edgar Markov"
    assert data["combo_count"] == 1
    assert data["combos"][0]["bracket"] == "2"
    assert data["use_guidance"]["mandatory_includes"] is False


def test_cli_combos_writes_file(tmp_path, monkeypatch):
    from typer.testing import CliRunner
    from mtgcli.cli import app

    out_file = tmp_path / "combos.json"
    monkeypatch.setenv("COMBOURL", "https://example.com/combos/")
    with patch("mtgcli.combos.fetcher.load_dotenv"), \
         patch("mtgcli.combos.fetcher.requests.get", return_value=_mock_response(200, _make_cli_raw())):
        runner = CliRunner()
        result = runner.invoke(app, [
            "combos",
            "--commander", "Edgar Markov",
            "--output", str(out_file),
            "--json-output",
        ])

    assert result.exit_code == 0, result.output
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert data["combo_count"] == 1


def test_cli_no_write_does_not_create_file(tmp_path, monkeypatch):
    from typer.testing import CliRunner
    from mtgcli.cli import app

    out_file = tmp_path / "combos.json"
    monkeypatch.setenv("COMBOURL", "https://example.com/combos/")
    with patch("mtgcli.combos.fetcher.load_dotenv"), \
         patch("mtgcli.combos.fetcher.requests.get", return_value=_mock_response(200, _make_cli_raw())):
        runner = CliRunner()
        runner.invoke(app, [
            "combos",
            "--commander", "Edgar Markov",
            "--output", str(out_file),
            "--no-write",
            "--json-output",
        ])

    assert not out_file.exists()


def test_cli_missing_combourl_exits_cleanly(monkeypatch):
    from typer.testing import CliRunner
    from mtgcli.cli import app

    monkeypatch.delenv("COMBOURL", raising=False)
    with patch("mtgcli.combos.fetcher.load_dotenv"):
        runner = CliRunner()
        result = runner.invoke(app, [
            "combos",
            "--commander", "Edgar Markov",
            "--no-write",
            "--json-output",
        ])

    assert result.exit_code != 0
    assert "Configuration error" in result.output


def test_cli_empty_combos_no_write(monkeypatch, tmp_path):
    from typer.testing import CliRunner
    from mtgcli.cli import app

    out_file = tmp_path / "combos.json"
    empty_raw = {"container": {"json_dict": {"cardlists": []}}}
    monkeypatch.setenv("COMBOURL", "https://example.com/combos/")
    with patch("mtgcli.combos.fetcher.load_dotenv"), \
         patch("mtgcli.combos.fetcher.requests.get", return_value=_mock_response(200, empty_raw)):
        runner = CliRunner()
        result = runner.invoke(app, [
            "combos",
            "--commander", "Edgar Markov",
            "--output", str(out_file),
            "--json-output",
        ])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["combo_count"] == 0
    assert not out_file.exists()


def test_cli_limit_filter(monkeypatch):
    from typer.testing import CliRunner
    from mtgcli.cli import app

    raw = {
        "container": {
            "json_dict": {
                "cardlists": [
                    {"cardviews": [{"name": "A"}, {"name": "B"}], "combo": {"results": [], "comboVote": None}},
                    {"cardviews": [{"name": "C"}, {"name": "D"}], "combo": {"results": [], "comboVote": None}},
                    {"cardviews": [{"name": "E"}, {"name": "F"}], "combo": {"results": [], "comboVote": None}},
                ]
            }
        }
    }
    monkeypatch.setenv("COMBOURL", "https://example.com/combos/")
    with patch("mtgcli.combos.fetcher.load_dotenv"), \
         patch("mtgcli.combos.fetcher.requests.get", return_value=_mock_response(200, raw)):
        runner = CliRunner()
        result = runner.invoke(app, [
            "combos",
            "--commander", "Edgar Markov",
            "--limit", "2",
            "--no-write",
            "--json-output",
        ])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["combo_count"] == 2
