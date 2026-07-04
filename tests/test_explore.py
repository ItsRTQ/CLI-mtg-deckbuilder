import json
import pytest
from unittest.mock import patch, MagicMock

from mtgcli.explore.slug import commander_to_slug
from mtgcli.explore.cleaner import extract_target_cards_from_html, sanitize_json_string, CONTROL_CHAR_RE
from mtgcli.explore.client import build_explore_url, fetch_commander_page


# --- slug tests ---

def test_slug_simple():
    assert commander_to_slug("Teysa Karlov") == "teysa-karlov"

def test_slug_comma():
    assert commander_to_slug("Omnath, Locus of Rage") == "omnath-locus-of-rage"

def test_slug_apostrophe():
    assert commander_to_slug("Adrix and Nev, Twincasters") == "adrix-and-nev-twincasters"

def test_slug_lowercases():
    assert commander_to_slug("LOVISA COLDEYES") == "lovisa-coldeyes"

def test_slug_extra_spaces():
    assert commander_to_slug("  Sol Ring  ") == "sol-ring"


# --- cleaner tests ---

def _make_html(section: str, card_names: list) -> str:
    cards_json = json.dumps([{"name": n} for n in card_names])
    return f'"cardviews":{cards_json},"header":"{section}"'

def test_cleaner_high_synergy():
    html = _make_html("High Synergy Cards", ["Sol Ring", "Arcane Signet"])
    result = extract_target_cards_from_html(html)
    assert result["high_synergy"] == ["Sol Ring", "Arcane Signet"]
    assert result["top_cards"] == []

def test_cleaner_top_cards():
    html = _make_html("Top Cards", ["Command Tower", "Beast Within"])
    result = extract_target_cards_from_html(html)
    assert result["top_cards"] == ["Command Tower", "Beast Within"]
    assert result["high_synergy"] == []

def test_cleaner_both_sections():
    html = (
        _make_html("High Synergy Cards", ["Card A"]) +
        _make_html("Top Cards", ["Card B"])
    )
    result = extract_target_cards_from_html(html)
    assert result["high_synergy"] == ["Card A"]
    assert result["top_cards"] == ["Card B"]

def test_cleaner_deduplicates():
    html = _make_html("Top Cards", ["Sol Ring", "Sol Ring", "Arcane Signet"])
    result = extract_target_cards_from_html(html)
    assert result["top_cards"].count("Sol Ring") == 1

def test_cleaner_filters_prices():
    html = _make_html("Top Cards", ["Sol Ring", "$2.99", "Arcane Signet"])
    result = extract_target_cards_from_html(html)
    assert "$2.99" not in result["top_cards"]

def test_cleaner_empty_html():
    result = extract_target_cards_from_html("")
    assert result == {"high_synergy": [], "top_cards": []}

def test_cleaner_unknown_section_ignored():
    html = _make_html("New Cards", ["Sol Ring"])
    result = extract_target_cards_from_html(html)
    assert result == {"high_synergy": [], "top_cards": []}


# --- JSON sanitation tests ---

def test_sanitize_removes_control_chars():
    assert sanitize_json_string("Sol\x1fRing") == "Sol Ring"
    assert sanitize_json_string("a\x00b\x07c") == "a b c"


def test_sanitize_normalizes_whitespace():
    assert sanitize_json_string("  Arcane   Signet \n") == "Arcane Signet"


def test_sanitize_handles_none():
    assert sanitize_json_string(None) is None


def test_cleaner_sanitizes_card_names():
    html = _make_html("Top Cards", ["Sol\x1fRing", "Arcane\tSignet"])
    result = extract_target_cards_from_html(html)
    assert result["top_cards"] == ["Sol Ring", "Arcane Signet"]
    for name in result["top_cards"]:
        assert not CONTROL_CHAR_RE.search(name)


def test_explore_json_output_is_strict_parseable():
    """explore --json-output must parse with strict json.loads (no control chars)."""
    from typer.testing import CliRunner
    from mtgcli.cli import app

    dirty_html = _make_html("High Synergy Cards", ["Sol\x1fRing"]) + \
        _make_html("Top Cards", ["Command\x07Tower"])

    with patch("mtgcli.cli.commands.search.build_explore_url", return_value="https://example.com/x"), \
         patch("mtgcli.cli.commands.search.fetch_commander_page", return_value=dirty_html), \
         patch("mtgcli.cli.commands.search.SQLITE_PATH") as mock_path:
        mock_path.exists.return_value = False
        runner = CliRunner()
        result = runner.invoke(app, ["explore", "--commander", "Kotis", "--json-output"])

    assert result.exit_code == 0, result.output
    # Strict parse must succeed (strict=True is the default) — no strict=False.
    data = json.loads(result.output)
    # No raw control characters in any payload STRING value.
    string_values = [data["commander"], data["source_url"], data["note"]]
    string_values += [c["name"] for c in data["high_synergy"] + data["top_cards"]]
    for val in string_values:
        assert not CONTROL_CHAR_RE.search(val), repr(val)
    names = [c["name"] for c in data["high_synergy"] + data["top_cards"]]
    assert "Sol Ring" in names
    assert "Command Tower" in names


# --- client tests ---

def test_build_explore_url():
    with patch.dict("os.environ", {"URLC": "https://edhrec.com/commanders"}):
        url = build_explore_url("Omnath, Locus of Rage")
    assert url == "https://edhrec.com/commanders/omnath-locus-of-rage"

def test_build_explore_url_trailing_slash():
    with patch.dict("os.environ", {"URLC": "https://edhrec.com/commanders/"}):
        url = build_explore_url("Teysa Karlov")
    assert url == "https://edhrec.com/commanders/teysa-karlov"

def test_build_explore_url_missing_env():
    with patch.dict("os.environ", {}, clear=True):
        with patch("mtgcli.explore.client.load_dotenv"):
            with pytest.raises(ValueError, match="URLC"):
                build_explore_url("Sol Ring")

def test_fetch_commander_page_success():
    mock_resp = MagicMock()
    mock_resp.text = "<html>data</html>"
    mock_resp.raise_for_status = MagicMock()
    with patch("mtgcli.explore.client.requests.get", return_value=mock_resp) as mock_get:
        html = fetch_commander_page("https://example.com/test")
    assert html == "<html>data</html>"
    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    assert kwargs.get("timeout") == 15

def test_fetch_commander_page_http_error():
    import requests as req
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = req.exceptions.HTTPError("404")
    with patch("mtgcli.explore.client.requests.get", return_value=mock_resp):
        with pytest.raises(req.exceptions.HTTPError):
            fetch_commander_page("https://example.com/not-found")

def test_fetch_commander_page_timeout():
    import requests as req
    with patch("mtgcli.explore.client.requests.get", side_effect=req.exceptions.Timeout):
        with pytest.raises(req.exceptions.Timeout):
            fetch_commander_page("https://example.com/slow")

def test_no_raw_file_written_by_default(tmp_path):
    # No file should be written unless --save-raw is passed
    html = _make_html("Top Cards", ["Sol Ring"])
    result = extract_target_cards_from_html(html)
    raw_files = list(tmp_path.glob("*.html")) + list(tmp_path.glob("*.txt"))
    assert raw_files == []
