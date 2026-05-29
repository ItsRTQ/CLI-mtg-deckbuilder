from mtgcli.export.moxfield import export_moxfield_line, export_deck_to_moxfield
from pathlib import Path


def test_export_moxfield_line_simple():
    card = {"name": "Sol Ring"}
    assert export_moxfield_line(card) == "1 Sol Ring"


def test_export_moxfield_line_with_quantity():
    card = {"name": "Forest", "quantity": 10}
    assert export_moxfield_line(card, quantity=10) == "10 Forest"


def test_export_moxfield_line_no_set_code():
    # set_code and collector_number are ignored; output is always simple format
    card = {"name": "Sol Ring", "set_code": "lcc", "collector_number": "299"}
    assert export_moxfield_line(card) == "1 Sol Ring"


def test_export_deck_to_moxfield(tmp_path):
    deck = [
        {"name": "Sol Ring", "quantity": 1},
        {"name": "Command Tower", "quantity": 1},
        {"name": "Forest", "quantity": 5},
    ]
    out = tmp_path / "deck.txt"
    export_deck_to_moxfield(deck, out)
    lines = out.read_text().strip().splitlines()
    assert lines == ["1 Sol Ring", "1 Command Tower", "5 Forest"]
