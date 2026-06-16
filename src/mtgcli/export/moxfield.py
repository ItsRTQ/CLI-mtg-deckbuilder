from pathlib import Path
from typing import List, Dict, Any, Optional


def export_moxfield_line(card: Dict[str, Any], quantity: int = 1) -> str:
    """Formats a single card line for Moxfield export: '1 Card Name'"""
    name = card.get("name")
    if not name:
        return ""
    return f"{quantity} {name}"


def export_deck_to_moxfield(
    deck_cards: List[Dict[str, Any]],
    output_path: Path,
    commanders: Optional[List[str]] = None,
) -> Path:
    """Exports a list of card dictionaries to a Moxfield-compatible text file.

    When ``commanders`` are given, they are written under a ``Commander`` section
    header (with the rest under ``Deck``), which Moxfield's bulk import recognizes,
    so the commander imports into the command zone instead of being dropped. With no
    commanders the output is the bare card list (unchanged, header-free).
    """
    commanders = commanders or []
    lines: List[str] = []

    if commanders:
        lines.append("Commander")
        for name in commanders:
            if name:
                lines.append(f"1 {name}")
        lines.append("")
        lines.append("Deck")

    for card in deck_cards:
        quantity = card.get("quantity", 1)
        line = export_moxfield_line(card, quantity)
        if line:
            lines.append(line)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return output_path
