import json
import pytest
from pathlib import Path
from mtgcli.export.final_builds import (
    sanitize_filename_part,
    normalize_bracket,
    next_final_build_path,
    save_final_build,
    deck_entries_to_moxfield_text,
)
from mtgcli.config import FINAL_BUILDS_DIR


# --- .gitkeep ---

def test_gitkeep_exists():
    assert (FINAL_BUILDS_DIR / ".gitkeep").exists()


# --- sanitize_filename_part ---

def test_sanitize_simple():
    assert sanitize_filename_part("Edgar Markov") == "Edgar-Markov"

def test_sanitize_comma():
    assert sanitize_filename_part("Omnath, Locus of Rage") == "Omnath-Locus-of-Rage"

def test_sanitize_apostrophe():
    assert sanitize_filename_part("Chishiro, the Shattered Blade") == "Chishiro-the-Shattered-Blade"

def test_sanitize_preserves_case():
    assert sanitize_filename_part("Teysa Karlov") == "Teysa-Karlov"

def test_sanitize_collapses_hyphens():
    assert sanitize_filename_part("Foo  Bar") == "Foo-Bar"

def test_sanitize_trims():
    assert sanitize_filename_part("  Sol Ring  ") == "Sol-Ring"


# --- normalize_bracket ---

def test_bracket_direct_t1():
    assert normalize_bracket(bracket="T1") == "T1"

def test_bracket_direct_t4():
    assert normalize_bracket(bracket="T4") == "T4"

def test_bracket_case_insensitive():
    assert normalize_bracket(bracket="t2") == "T2"

def test_bracket_from_power_casual():
    assert normalize_bracket(power_level="casual") == "T4"

def test_bracket_from_power_competitive():
    assert normalize_bracket(power_level="competitive") == "T1"

def test_bracket_from_power_highly_optimized():
    assert normalize_bracket(power_level="highly_optimized") == "T2"

def test_bracket_from_power_precon_optimized():
    assert normalize_bracket(power_level="precon_optimized") == "T3"

def test_bracket_default_when_none():
    assert normalize_bracket() == "T4"

def test_bracket_default_when_unknown():
    assert normalize_bracket(power_level="mystery_level") == "T4"

def test_bracket_direct_takes_precedence():
    assert normalize_bracket(power_level="casual", bracket="T1") == "T1"


# --- next_final_build_path ---

def test_first_build_is_v1(tmp_path):
    path = next_final_build_path("Edgar Markov", "Tribal", "T4", tmp_path)
    assert path.name == "Edgar-Markov-Tribal-T4-v1.txt"

def test_existing_v1_creates_v2(tmp_path):
    (tmp_path / "Edgar-Markov-Tribal-T4-v1.txt").write_text("deck")
    path = next_final_build_path("Edgar Markov", "Tribal", "T4", tmp_path)
    assert path.name == "Edgar-Markov-Tribal-T4-v2.txt"

def test_existing_v1_v2_v3_creates_v4(tmp_path):
    for v in [1, 2, 3]:
        (tmp_path / f"Edgar-Markov-Tribal-T4-v{v}.txt").write_text("deck")
    path = next_final_build_path("Edgar Markov", "Tribal", "T4", tmp_path)
    assert path.name == "Edgar-Markov-Tribal-T4-v4.txt"

def test_does_not_overwrite(tmp_path):
    first = save_final_build("deck1\n", "Edgar Markov", "Tribal", "T4", tmp_path)
    second = save_final_build("deck2\n", "Edgar Markov", "Tribal", "T4", tmp_path)
    assert first != second
    assert first.read_text() == "deck1\n"
    assert second.read_text() == "deck2\n"


# --- save_final_build ---

def test_save_creates_file(tmp_path):
    path = save_final_build("1 Sol Ring\n1 Command Tower\n", "Teysa Karlov", "Aristocrats", "T3", tmp_path)
    assert path.exists()
    assert path.read_text() == "1 Sol Ring\n1 Command Tower\n"

def test_save_simple_moxfield_format(tmp_path):
    entries = [{"name": "Sol Ring", "quantity": 1}, {"name": "Command Tower", "quantity": 1}]
    text = deck_entries_to_moxfield_text(entries)
    assert "Sol Ring" in text
    assert "Command Tower" in text
    assert "set_code" not in text
    assert text.startswith("1 Sol Ring")


# --- deck_entries_to_moxfield_text ---

def test_moxfield_text_format():
    entries = [{"name": "Sol Ring", "quantity": 1}, {"name": "Forest", "quantity": 5}]
    text = deck_entries_to_moxfield_text(entries)
    lines = text.strip().splitlines()
    assert lines[0] == "1 Sol Ring"
    assert lines[1] == "5 Forest"

def test_moxfield_text_skips_empty_names():
    entries = [{"name": "", "quantity": 1}, {"name": "Sol Ring", "quantity": 1}]
    text = deck_entries_to_moxfield_text(entries)
    lines = text.strip().splitlines()
    assert len(lines) == 1
    assert lines[0] == "1 Sol Ring"
