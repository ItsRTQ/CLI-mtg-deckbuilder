import json
import pytest
from pathlib import Path
from mtgcli.utils.temp_cleaner import (
    clean_output_files,
    find_normal_temp_files,
    find_full_clean_files,
    ALWAYS_PRESERVE,
    PROTECTED_NORMAL_FILES,
)


def _make_files(directory: Path, names: list) -> None:
    for name in names:
        (directory / name).write_text("content")


# --- find_normal_temp_files ---

def test_normal_finds_temp_patterns(tmp_path):
    _make_files(tmp_path, ["deck.working.json", "commander-raw-data.txt", "omnath-raw.html"])
    found = find_normal_temp_files(tmp_path)
    assert len(found) == 3

def test_normal_excludes_protected(tmp_path):
    _make_files(tmp_path, ["deck.json", "deck.enriched.json", "deck.moxfield.txt"])
    found = find_normal_temp_files(tmp_path)
    assert found == []

def test_normal_excludes_gitkeep(tmp_path):
    _make_files(tmp_path, [".gitkeep", "deck.debug.json"])
    found = find_normal_temp_files(tmp_path)
    names = [p.name for p in found]
    assert ".gitkeep" not in names
    assert "deck.debug.json" in names

def test_normal_missing_dir():
    assert find_normal_temp_files(Path("/nonexistent/path")) == []


# --- find_full_clean_files ---

def test_full_includes_final_artifacts(tmp_path):
    _make_files(tmp_path, ["deck.json", "deck.enriched.json", "deck.moxfield.txt"])
    found = find_full_clean_files(tmp_path)
    assert len(found) == 3

def test_full_excludes_gitkeep(tmp_path):
    _make_files(tmp_path, [".gitkeep", "deck.json"])
    found = find_full_clean_files(tmp_path)
    names = [p.name for p in found]
    assert ".gitkeep" not in names
    assert "deck.json" in names

def test_full_missing_dir():
    assert find_full_clean_files(Path("/nonexistent/path")) == []


# --- clean_output_files: normal mode ---

def test_normal_clean_deletes_temp(tmp_path):
    _make_files(tmp_path, ["deck.working.json", "omnath-raw.html", "deck.json"])
    report = clean_output_files(tmp_path, full=False, dry_run=False)
    assert report["deleted_count"] == 2
    assert (tmp_path / "deck.json").exists()
    assert not (tmp_path / "deck.working.json").exists()
    assert not (tmp_path / "omnath-raw.html").exists()

def test_normal_clean_preserves_final_artifacts(tmp_path):
    _make_files(tmp_path, ["deck.json", "deck.enriched.json", "deck.moxfield.txt",
                            "deck_explanation.md", "validation_report.json"])
    report = clean_output_files(tmp_path, full=False, dry_run=False)
    assert report["deleted_count"] == 0
    for name in ["deck.json", "deck.enriched.json", "deck.moxfield.txt",
                 "deck_explanation.md", "validation_report.json"]:
        assert (tmp_path / name).exists()

def test_normal_clean_preserves_gitkeep(tmp_path):
    _make_files(tmp_path, [".gitkeep", "deck.cache"])
    clean_output_files(tmp_path, full=False, dry_run=False)
    assert (tmp_path / ".gitkeep").exists()

def test_normal_clean_nothing_to_delete(tmp_path):
    _make_files(tmp_path, ["deck.json"])
    report = clean_output_files(tmp_path, full=False, dry_run=False)
    assert report["deleted_count"] == 0
    assert report["matched_count"] == 0


# --- clean_output_files: dry run ---

def test_dry_run_does_not_delete(tmp_path):
    _make_files(tmp_path, ["deck.working.json", "omnath-raw.html"])
    report = clean_output_files(tmp_path, full=False, dry_run=True)
    assert report["dry_run"] is True
    assert report["deleted_count"] == 0
    assert report["matched_count"] == 2
    assert (tmp_path / "deck.working.json").exists()
    assert (tmp_path / "omnath-raw.html").exists()

def test_full_dry_run_does_not_delete(tmp_path):
    _make_files(tmp_path, [".gitkeep", "deck.json", "deck.moxfield.txt"])
    report = clean_output_files(tmp_path, full=True, dry_run=True)
    assert report["dry_run"] is True
    assert report["deleted_count"] == 0
    assert report["matched_count"] == 2
    assert (tmp_path / "deck.json").exists()


# --- clean_output_files: full mode ---

def test_full_clean_deletes_final_artifacts(tmp_path):
    _make_files(tmp_path, [".gitkeep", "deck.json", "deck.enriched.json",
                            "deck.moxfield.txt", "deck_explanation.md", "validation_report.json"])
    report = clean_output_files(tmp_path, full=True, dry_run=False)
    assert report["deleted_count"] == 5
    assert (tmp_path / ".gitkeep").exists()
    for name in ["deck.json", "deck.enriched.json", "deck.moxfield.txt",
                 "deck_explanation.md", "validation_report.json"]:
        assert not (tmp_path / name).exists()

def test_full_clean_always_preserves_gitkeep(tmp_path):
    _make_files(tmp_path, [".gitkeep", "deck.json"])
    clean_output_files(tmp_path, full=True, dry_run=False)
    assert (tmp_path / ".gitkeep").exists()


# --- report shape ---

def test_report_has_required_keys(tmp_path):
    _make_files(tmp_path, ["deck.json", "deck.working.json"])
    report = clean_output_files(tmp_path, full=False, dry_run=True)
    for key in ["output_dir", "mode", "dry_run", "deleted_count", "matched_count",
                "preserved_files", "files"]:
        assert key in report

def test_report_mode_field(tmp_path):
    report_normal = clean_output_files(tmp_path, full=False, dry_run=True)
    report_full = clean_output_files(tmp_path, full=True, dry_run=True)
    assert report_normal["mode"] == "normal"
    assert report_full["mode"] == "full"

def test_report_is_json_serializable(tmp_path):
    _make_files(tmp_path, [".gitkeep", "deck.json", "deck.tmp"])
    report = clean_output_files(tmp_path, full=True, dry_run=True)
    serialized = json.dumps(report)
    parsed = json.loads(serialized)
    assert parsed["mode"] == "full"


# --- missing output directory ---

def test_missing_dir_returns_gracefully():
    report = clean_output_files(Path("/nonexistent/output"), full=False, dry_run=False)
    assert report["deleted_count"] == 0
    assert report["matched_count"] == 0
    assert "error" in report

def test_missing_dir_full_mode():
    report = clean_output_files(Path("/nonexistent/output"), full=True, dry_run=False)
    assert report["deleted_count"] == 0
    assert "error" in report


# --- safety: never deletes outside output_dir ---

def test_does_not_escape_output_dir(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    outside_file = tmp_path / "important.json"
    outside_file.write_text("do not delete")
    _make_files(output_dir, ["deck.working.json"])
    clean_output_files(output_dir, full=True, dry_run=False)
    assert outside_file.exists()
