from pathlib import Path
from typing import List, Dict, Any
import fnmatch

TEMP_PATTERNS = [
    "*.tmp",
    "*.temp",
    "*.bak",
    "*.log",
    "*.cache",
    "*-raw.html",
    "*-raw.txt",
    "*raw-data.txt",
    "pull-context.txt",
    "commander-raw-data.txt",
    "*.debug.json",
    "*.intermediate.json",
    "*.working.json",
]

PROTECTED_NORMAL_FILES = {
    "deck.json",
    "deck.enriched.json",
    "deck.moxfield.txt",
    "deck_explanation.md",
    "validation_report.json",
    ".gitkeep",
}

ALWAYS_PRESERVE = {".gitkeep"}


def _matches_temp_pattern(name: str) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in TEMP_PATTERNS)


def find_normal_temp_files(output_dir: Path) -> List[Path]:
    """Returns files matching temp patterns, excluding protected files."""
    if not output_dir.exists():
        return []
    return [
        p for p in output_dir.iterdir()
        if p.is_file()
        and p.name not in PROTECTED_NORMAL_FILES
        and _matches_temp_pattern(p.name)
    ]


def find_full_clean_files(output_dir: Path) -> List[Path]:
    """Returns all files in output_dir except ALWAYS_PRESERVE."""
    if not output_dir.exists():
        return []
    return [
        p for p in output_dir.iterdir()
        if p.is_file() and p.name not in ALWAYS_PRESERVE
    ]


def clean_output_files(
    output_dir: Path,
    full: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Scans output_dir and optionally deletes matched files.

    Returns a report dict with matched files, preserved files, and delete count.
    """
    if not output_dir.exists():
        return {
            "output_dir": str(output_dir),
            "mode": "full" if full else "normal",
            "dry_run": dry_run,
            "deleted_count": 0,
            "matched_count": 0,
            "preserved_files": [],
            "files": [],
            "error": f"Output directory '{output_dir}' does not exist.",
        }

    all_files = [p for p in output_dir.iterdir() if p.is_file()]

    if full:
        to_delete = [p for p in all_files if p.name not in ALWAYS_PRESERVE]
        preserved = [p for p in all_files if p.name in ALWAYS_PRESERVE]
    else:
        to_delete = [
            p for p in all_files
            if p.name not in PROTECTED_NORMAL_FILES and _matches_temp_pattern(p.name)
        ]
        preserved = [p for p in all_files if p.name in PROTECTED_NORMAL_FILES or p.name in ALWAYS_PRESERVE]

    deleted_count = 0
    if not dry_run:
        for p in to_delete:
            p.unlink()
            deleted_count += 1

    return {
        "output_dir": str(output_dir),
        "mode": "full" if full else "normal",
        "dry_run": dry_run,
        "deleted_count": deleted_count,
        "matched_count": len(to_delete),
        "preserved_files": sorted(str(p) for p in preserved),
        "files": sorted(str(p) for p in to_delete),
    }
