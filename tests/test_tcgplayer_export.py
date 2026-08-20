"""TCGplayer Mass Entry export: pure helpers + `mtg export-tcgplayer` CLI."""
import json
import webbrowser

from typer.testing import CliRunner

from mtgcli.cli import app
from mtgcli.export.tcgplayer import (
    build_tcgplayer_entries,
    build_tcgplayer_mass_entry_url,
    normalize_deck_for_tcgplayer,
)

runner = CliRunner()


# ── normalize_deck_for_tcgplayer ──────────────────────────────────────────────

def test_normalize_merges_duplicates():
    cards, skipped = normalize_deck_for_tcgplayer(
        [{"name": "Sol Ring", "quantity": 1}, {"name": "Sol Ring", "quantity": 1}])
    assert cards == [{"name": "Sol Ring", "quantity": 2}]
    assert skipped == []


def test_normalize_skips_invalid_entries():
    cards, skipped = normalize_deck_for_tcgplayer([
        {"name": "Sol Ring", "quantity": 0},
        {"name": "Arcane Signet", "quantity": -1},
        {"name": "", "quantity": 1},
        {"name": "Bad Qty", "quantity": "x"},
        {"name": "Command Tower", "quantity": 1},
    ])
    assert cards == [{"name": "Command Tower", "quantity": 1}]
    assert len(skipped) == 4


def test_normalize_commander_first_and_deduped():
    cards, _ = normalize_deck_for_tcgplayer(
        [{"name": "Sol Ring", "quantity": 1},
         {"name": "Shorikai, Genesis Engine", "quantity": 1}],
        commanders=["Shorikai, Genesis Engine"])
    # Commander leads at qty 1; its main-deck duplicate (same physical card) drops.
    assert cards == [
        {"name": "Shorikai, Genesis Engine", "quantity": 1},
        {"name": "Sol Ring", "quantity": 1},
    ]


_LAYOUTS = {
    "Wear // Tear": "split",
    "Cut // Ribbons": "split",          # aftermath is layout `split` in the DB
    "Valakut Awakening // Valakut Stoneforge": "modal_dfc",
    "Delver of Secrets // Insectile Aberration": "transform",
    "Bonecrusher Giant // Stomp": "adventure",
}


def test_normalize_split_keeps_full_name():
    # TCGplayer product titles for split/aftermath keep both halves
    # ("Wear // Tear") — front-face-only would not match a product.
    cards, _ = normalize_deck_for_tcgplayer([
        {"name": "Wear // Tear", "quantity": 1},
        {"name": "Cut // Ribbons", "quantity": 1},
    ], layout_lookup=_LAYOUTS.get)
    assert [c["name"] for c in cards] == ["Wear // Tear", "Cut // Ribbons"]


def test_normalize_reduces_non_split_layouts_to_front_face():
    cards, _ = normalize_deck_for_tcgplayer([
        {"name": "Valakut Awakening // Valakut Stoneforge", "quantity": 1},
        {"name": "Delver of Secrets // Insectile Aberration", "quantity": 1},
        {"name": "Bonecrusher Giant // Stomp", "quantity": 1},
    ], layout_lookup=_LAYOUTS.get)
    assert [c["name"] for c in cards] == [
        "Valakut Awakening", "Delver of Secrets", "Bonecrusher Giant"]


def test_normalize_without_lookup_defaults_to_front_face():
    cards, _ = normalize_deck_for_tcgplayer([
        {"name": "Valakut Awakening // Valakut Stoneforge", "quantity": 1},
    ])
    assert [c["name"] for c in cards] == ["Valakut Awakening"]


def test_normalize_preserves_punctuation():
    names = ["Urza's Saga", "Boseiju, Who Endures", "Lim-Dûl's Vault"]
    cards, _ = normalize_deck_for_tcgplayer(
        [{"name": n, "quantity": 1} for n in names])
    assert [c["name"] for c in cards] == names


# ── entries + URL ─────────────────────────────────────────────────────────────

_THREE = [{"name": "Sol Ring", "quantity": 1},
          {"name": "Arcane Signet", "quantity": 1},
          {"name": "Command Tower", "quantity": 1}]


def test_entries_format():
    assert build_tcgplayer_entries(_THREE) == [
        "1 Sol Ring", "1 Arcane Signet", "1 Command Tower"]


def test_payload_has_leading_separator():
    # The unencoded payload starts with "||" before the first card.
    url = build_tcgplayer_mass_entry_url(_THREE)
    assert "c=%7C%7C1+Sol+Ring%7C%7C1+Arcane+Signet%7C%7C1+Command+Tower" in url


def test_url_shape_and_single_pass_encoding():
    url = build_tcgplayer_mass_entry_url(
        [{"name": "Shorikai, Genesis Engine", "quantity": 1}])
    assert url.startswith("https://www.tcgplayer.com/massentry?")
    assert "productline=Magic" in url
    assert "Shorikai%2C+Genesis+Engine" in url
    assert "%252C" not in url            # no double encoding
    assert "1 Shorikai" not in url       # no raw unencoded list
    assert "||" not in url


# ── CLI: mtg export-tcgplayer ─────────────────────────────────────────────────

def _decklist(tmp_path):
    p = tmp_path / "deck.txt"
    p.write_text("1 Sol Ring\n1 Arcane Signet\n1 Command Tower\n", encoding="utf-8")
    return p


def _opened(monkeypatch, result=True):
    calls = []

    def fake_open(url):
        calls.append(url)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(webbrowser, "open", fake_open)
    return calls


def test_cli_opens_browser_with_url(tmp_path, monkeypatch):
    calls = _opened(monkeypatch)
    r = runner.invoke(app, ["export-tcgplayer", str(_decklist(tmp_path))])
    assert r.exit_code == 0, r.output
    assert calls == [build_tcgplayer_mass_entry_url(_THREE)]
    assert "TCGplayer export created for 3 cards." in r.output
    assert "Opening TCGplayer Mass Entry" in r.output


def test_cli_print_url_skips_browser(tmp_path, monkeypatch):
    calls = _opened(monkeypatch)
    r = runner.invoke(app, ["export-tcgplayer", str(_decklist(tmp_path)), "--print-url"])
    assert r.exit_code == 0, r.output
    assert not calls
    assert build_tcgplayer_mass_entry_url(_THREE) in r.output


def test_cli_browser_failure_is_partial_success(tmp_path, monkeypatch):
    _opened(monkeypatch, result=False)
    r = runner.invoke(app, ["export-tcgplayer", str(_decklist(tmp_path))])
    assert r.exit_code == 0, r.output
    assert "browser could not be opened" in r.output
    assert build_tcgplayer_mass_entry_url(_THREE) in r.output


def test_cli_browser_exception_is_partial_success(tmp_path, monkeypatch):
    _opened(monkeypatch, result=RuntimeError("no display"))
    r = runner.invoke(app, ["export-tcgplayer", str(_decklist(tmp_path))])
    assert r.exit_code == 0, r.output
    assert build_tcgplayer_mass_entry_url(_THREE) in r.output


def test_cli_json_output(tmp_path, monkeypatch):
    _opened(monkeypatch)
    r = runner.invoke(app, ["export-tcgplayer", str(_decklist(tmp_path)),
                            "--print-url", "--json-output"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert data["ok"] is True
    assert data["card_count"] == 3
    assert data["skipped"] == []
    assert data["opened_browser"] is False
    assert data["url"] == build_tcgplayer_mass_entry_url(_THREE)


def test_cli_json_deck_includes_commander(tmp_path, monkeypatch):
    _opened(monkeypatch)
    deck = tmp_path / "deck.json"
    deck.write_text(json.dumps({
        "commander": "Shorikai, Genesis Engine",
        "main_deck": [{"name": "Sol Ring", "quantity": 1}],
    }), encoding="utf-8")
    r = runner.invoke(app, ["export-tcgplayer", str(deck), "--print-url", "--json-output"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert data["card_count"] == 2
    assert "Shorikai%2C+Genesis+Engine" in data["url"]


def test_cli_missing_file_exits_one():
    r = runner.invoke(app, ["export-tcgplayer", "nope/missing.txt"])
    assert r.exit_code == 1


def test_cli_empty_deck_exits_one(tmp_path, monkeypatch):
    _opened(monkeypatch)
    p = tmp_path / "empty.txt"
    p.write_text("# just a comment\n", encoding="utf-8")
    r = runner.invoke(app, ["export-tcgplayer", str(p), "--json-output"])
    assert r.exit_code == 1
    data = json.loads(r.output)
    assert data["error"]["type"] == "validation"
    assert "No valid cards" in data["error"]["message"]
