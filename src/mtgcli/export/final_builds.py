import re
from pathlib import Path
from typing import Optional, List, Dict, Any

_BRACKET_MAP = {
    "cedh": "T1",
    "c_edh": "T1",
    "competitive": "T1",
    "high_power": "T2",
    "high power": "T2",
    "highly optimized": "T2",
    "highly_optimized": "T2",
    "optimized casual": "T3",
    "optimized_casual": "T3",
    "slightly optimized": "T3",
    "slightly_optimized": "T3",
    "precon optimized": "T3",
    "precon_optimized": "T3",
    "casual": "T4",
    "precon": "T4",
    "precon level": "T4",
    "precon_level": "T4",
}

_VALID_BRACKETS = {"T1", "T2", "T3", "T4"}


def sanitize_filename_part(value: str) -> str:
    """Converts a string into a safe, readable filename segment.

    Example: 'Omnath, Locus of Rage' -> 'Omnath-Locus-of-Rage'
    """
    value = re.sub(r"[''`\"']", "", value)
    value = re.sub(r"[^A-Za-z0-9\s-]", "", value)
    value = re.sub(r"\s+", "-", value.strip())
    value = re.sub(r"-+", "-", value)
    return value.strip("-")


def normalize_bracket(power_level: Optional[str] = None, bracket: Optional[str] = None) -> str:
    """Returns a T1-T4 bracket string.

    Accepts either a bracket like 'T4' directly, or a power_level label like 'casual'.
    Defaults to T4 if nothing valid is provided.
    """
    if bracket:
        b = bracket.strip().upper()
        if b in _VALID_BRACKETS:
            return b

    if power_level:
        key = power_level.strip().lower()
        if key in _BRACKET_MAP:
            return _BRACKET_MAP[key]

    return "T4"


def next_final_build_path(
    commander: str,
    theme: str,
    bracket: str,
    final_builds_dir: Path = Path("final-builds"),
) -> Path:
    """Returns the next available versioned path for a final build file."""
    final_builds_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{sanitize_filename_part(commander)}-{sanitize_filename_part(theme)}-{bracket}"
    version = 1
    while True:
        candidate = final_builds_dir / f"{prefix}-v{version}.txt"
        if not candidate.exists():
            return candidate
        version += 1


def save_final_build(
    decklist_text: str,
    commander: str,
    theme: str,
    bracket: str,
    final_builds_dir: Path = Path("final-builds"),
) -> Path:
    """Saves a Moxfield-format decklist to final-builds/ with a versioned filename."""
    path = next_final_build_path(commander, theme, bracket, final_builds_dir)
    path.write_text(decklist_text, encoding="utf-8")
    return path


def deck_entries_to_moxfield_text(deck_entries: List[Dict[str, Any]]) -> str:
    """Converts a list of deck entry dicts to simple Moxfield text."""
    lines = []
    for entry in deck_entries:
        name = entry.get("name", "").strip()
        quantity = entry.get("quantity", 1)
        if name:
            lines.append(f"{quantity} {name}")
    return "\n".join(lines) + "\n" if lines else ""
