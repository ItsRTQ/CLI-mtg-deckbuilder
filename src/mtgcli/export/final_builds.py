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


def next_final_build_name(
    commander: str,
    theme: str,
    bracket: str,
    final_builds_dir: Path = Path("final-builds"),
) -> str:
    """Returns the next available versioned build name, checking for existing directories."""
    final_builds_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{sanitize_filename_part(commander)}-{sanitize_filename_part(theme)}-{bracket}"
    version = 1
    while True:
        candidate_name = f"{prefix}-v{version}"
        if not (final_builds_dir / candidate_name).exists():
            return candidate_name
        version += 1


def next_final_build_path(
    commander: str,
    theme: str,
    bracket: str,
    final_builds_dir: Path = Path("final-builds"),
) -> Path:
    """Backward-compatible: returns the decklist path inside the next available build dir."""
    build_name = next_final_build_name(commander, theme, bracket, final_builds_dir)
    return final_builds_dir / build_name / f"{build_name}.txt"


def create_final_build_directory(
    build_name: str,
    final_builds_dir: Path = Path("final-builds"),
) -> Path:
    """Creates the versioned sub-directory for a final build. Never overwrites."""
    build_dir = final_builds_dir / build_name
    build_dir.mkdir(parents=True, exist_ok=False)
    return build_dir


def save_final_build_decklist(
    decklist_text: str,
    build_dir: Path,
    build_name: str,
) -> Path:
    """Saves the Moxfield decklist .txt inside the build directory."""
    path = build_dir / f"{build_name}.txt"
    path.write_text(decklist_text, encoding="utf-8")
    return path


def save_final_build_explanation(
    explanation_text: str,
    build_dir: Path,
    build_name: str,
) -> Path:
    """Saves the explanation .md inside the build directory."""
    path = build_dir / f"{build_name}.explanation.md"
    path.write_text(explanation_text, encoding="utf-8")
    return path


def build_minimal_explanation(
    commander: str,
    theme: str,
    bracket: str,
    partner: Optional[str] = None,
) -> str:
    """Generates a minimal explanation stub when no explanation file was provided."""
    commander_line = f"{commander} / {partner}" if partner else commander
    return (
        f"# Deck Explanation: {commander_line} — {theme}\n\n"
        f"- **Commander:** {commander_line}\n"
        f"- **Theme:** {theme}\n"
        f"- **Bracket:** {bracket}\n"
        f"- **Validation:** Passed\n"
        f"- **Note:** No full explanation was provided for this build.\n\n"
        f"## Gameplan\n\n_Not documented._\n\n"
        f"## Key Packages\n\n_Not documented._\n\n"
        f"## Win Conditions\n\n_Not documented._\n\n"
        f"## Weaknesses\n\n_Not documented._\n"
    )


def save_final_build(
    decklist_text: str,
    commander: str,
    theme: str,
    bracket: str,
    final_builds_dir: Path = Path("final-builds"),
) -> Path:
    """
    Saves a decklist into a versioned sub-directory.
    Returns the decklist file path.
    """
    build_name = next_final_build_name(commander, theme, bracket, final_builds_dir)
    build_dir = create_final_build_directory(build_name, final_builds_dir)
    return save_final_build_decklist(decklist_text, build_dir, build_name)


def deck_entries_to_moxfield_text(deck_entries: List[Dict[str, Any]]) -> str:
    """Converts a list of deck entry dicts to simple Moxfield text."""
    lines = []
    for entry in deck_entries:
        name = entry.get("name", "").strip()
        quantity = entry.get("quantity", 1)
        if name:
            lines.append(f"{quantity} {name}")
    return "\n".join(lines) + "\n" if lines else ""
