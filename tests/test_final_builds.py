import json
import pytest
from pathlib import Path
from mtgcli.export.final_builds import (
    sanitize_filename_part,
    normalize_bracket,
    next_final_build_name,
    next_final_build_path,
    create_final_build_directory,
    save_final_build_decklist,
    save_final_build_explanation,
    build_minimal_explanation,
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


# --- next_final_build_name / versioning ---

def test_first_build_name_is_v1(tmp_path):
    name = next_final_build_name("Edgar Markov", "Tribal", "T4", tmp_path)
    assert name == "Edgar-Markov-Tribal-T4-v1"

def test_existing_v1_dir_creates_v2(tmp_path):
    (tmp_path / "Edgar-Markov-Tribal-T4-v1").mkdir()
    name = next_final_build_name("Edgar Markov", "Tribal", "T4", tmp_path)
    assert name == "Edgar-Markov-Tribal-T4-v2"

def test_existing_v1_v2_v3_dirs_creates_v4(tmp_path):
    for v in [1, 2, 3]:
        (tmp_path / f"Edgar-Markov-Tribal-T4-v{v}").mkdir()
    name = next_final_build_name("Edgar Markov", "Tribal", "T4", tmp_path)
    assert name == "Edgar-Markov-Tribal-T4-v4"

def test_next_final_build_path_points_inside_dir(tmp_path):
    path = next_final_build_path("Edgar Markov", "Tribal", "T4", tmp_path)
    assert path.parent.name == "Edgar-Markov-Tribal-T4-v1"
    assert path.name == "Edgar-Markov-Tribal-T4-v1.txt"


# --- create_final_build_directory ---

def test_create_build_directory(tmp_path):
    build_dir = create_final_build_directory("Edgar-Markov-Tribal-T4-v1", tmp_path)
    assert build_dir.exists()
    assert build_dir.is_dir()
    assert build_dir.name == "Edgar-Markov-Tribal-T4-v1"

def test_create_build_directory_fails_if_exists(tmp_path):
    create_final_build_directory("Edgar-Markov-Tribal-T4-v1", tmp_path)
    with pytest.raises(FileExistsError):
        create_final_build_directory("Edgar-Markov-Tribal-T4-v1", tmp_path)


# --- save_final_build_decklist + save_final_build_explanation ---

def test_save_decklist_inside_build_dir(tmp_path):
    build_dir = tmp_path / "Test-Theme-T4-v1"
    build_dir.mkdir()
    path = save_final_build_decklist("1 Sol Ring\n", build_dir, "Test-Theme-T4-v1")
    assert path.name == "Test-Theme-T4-v1.txt"
    assert path.read_text() == "1 Sol Ring\n"

def test_save_explanation_inside_build_dir(tmp_path):
    build_dir = tmp_path / "Test-Theme-T4-v1"
    build_dir.mkdir()
    path = save_final_build_explanation("# Explanation\n", build_dir, "Test-Theme-T4-v1")
    assert path.name == "Test-Theme-T4-v1.explanation.md"
    assert path.read_text() == "# Explanation\n"

def test_explanation_filename_matches_decklist_base(tmp_path):
    build_name = "Edgar-Markov-Tribal-T4-v1"
    build_dir = tmp_path / build_name
    build_dir.mkdir()
    decklist_path = save_final_build_decklist("decklist", build_dir, build_name)
    explanation_path = save_final_build_explanation("explanation", build_dir, build_name)
    assert decklist_path.stem == build_name
    assert explanation_path.name == f"{build_name}.explanation.md"


# --- save_final_build (integrated) ---

def test_save_final_build_creates_subfolder(tmp_path):
    path = save_final_build("1 Sol Ring\n", "Edgar Markov", "Tribal", "T4", tmp_path)
    assert path.parent.is_dir()
    assert path.parent.name == "Edgar-Markov-Tribal-T4-v1"

def test_save_final_build_decklist_in_subfolder(tmp_path):
    path = save_final_build("deck\n", "Edgar Markov", "Tribal", "T4", tmp_path)
    assert path.exists()
    assert path.read_text() == "deck\n"

def test_does_not_overwrite(tmp_path):
    first = save_final_build("deck1\n", "Edgar Markov", "Tribal", "T4", tmp_path)
    second = save_final_build("deck2\n", "Edgar Markov", "Tribal", "T4", tmp_path)
    assert first != second
    assert first.read_text() == "deck1\n"
    assert second.read_text() == "deck2\n"
    assert first.parent.name == "Edgar-Markov-Tribal-T4-v1"
    assert second.parent.name == "Edgar-Markov-Tribal-T4-v2"


# --- build_minimal_explanation ---

def test_minimal_explanation_contains_commander():
    text = build_minimal_explanation("Brago, King Eternal", "Blink", "T3")
    assert "Brago" in text

def test_minimal_explanation_contains_theme():
    text = build_minimal_explanation("Brago, King Eternal", "Blink", "T3")
    assert "Blink" in text

def test_minimal_explanation_contains_bracket():
    text = build_minimal_explanation("Brago, King Eternal", "Blink", "T3")
    assert "T3" in text

def test_minimal_explanation_with_partner():
    text = build_minimal_explanation("Tymna the Weaver", "Goodstuff", "T2", partner="Thrasios, Triton Hero")
    assert "Tymna" in text
    assert "Thrasios" in text

def test_minimal_explanation_is_markdown():
    text = build_minimal_explanation("Brago, King Eternal", "Blink", "T3")
    assert text.startswith("#")

def test_minimal_explanation_has_sections():
    text = build_minimal_explanation("Brago, King Eternal", "Blink", "T3")
    assert "## Gameplan" in text
    assert "## Win Conditions" in text


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

def test_moxfield_text_no_set_code():
    entries = [{"name": "Sol Ring", "quantity": 1}]
    text = deck_entries_to_moxfield_text(entries)
    assert "set_code" not in text
    assert text.startswith("1 Sol Ring")


# --- build_final_name: <commander>-<TIER>-<RANK>-<COST> + collision numbering ---

def test_build_final_name_new_convention(tmp_path):
    from mtgcli.export.final_builds import build_final_name
    n = build_final_name("Dihada, Binder of Wills", "+S", "Mythic", "4776usd", tmp_path)
    assert n == "Dihada-Binder-of-Wills-+S-Mythic-4776usd"


def test_build_final_name_collision_numbers_after_commander(tmp_path):
    from mtgcli.export.final_builds import build_final_name
    # first copy: numberless base
    n1 = build_final_name("Kess, Dissident Mage", "F", "Dormant", "760usd", tmp_path)
    (tmp_path / n1).mkdir()
    assert n1 == "Kess-Dissident-Mage-F-Dormant-760usd"
    # exact copy -> number right after the commander name, rising
    n2 = build_final_name("Kess, Dissident Mage", "F", "Dormant", "760usd", tmp_path)
    (tmp_path / n2).mkdir()
    assert n2 == "Kess-Dissident-Mage1-F-Dormant-760usd"
    n3 = build_final_name("Kess, Dissident Mage", "F", "Dormant", "760usd", tmp_path)
    assert n3 == "Kess-Dissident-Mage2-F-Dormant-760usd"
    # a DIFFERENT tier/rank/cost is not a collision -> its own numberless base
    other = build_final_name("Kess, Dissident Mage", "F", "Dormant", "999usd", tmp_path)
    assert other == "Kess-Dissident-Mage-F-Dormant-999usd"


def test_build_final_name_omits_missing_tier(tmp_path):
    from mtgcli.export.final_builds import build_final_name
    # unannotated deck: no TIER -> segment dropped entirely (not 'na')
    n = build_final_name("Dihada, Binder of Wills", None, "Mythic", "4776usd", tmp_path)
    assert n == "Dihada-Binder-of-Wills-Mythic-4776usd"
    # collision still numbers right after the commander
    (tmp_path / n).mkdir()
    n2 = build_final_name("Dihada, Binder of Wills", None, "Mythic", "4776usd", tmp_path)
    assert n2 == "Dihada-Binder-of-Wills1-Mythic-4776usd"
