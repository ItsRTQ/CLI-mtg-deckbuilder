from pathlib import Path
from typing import List, Dict, Any


def export_moxfield_line(card: Dict[str, Any], quantity: int = 1) -> str:
    """
    Formats a single card line for Moxfield export.
    Format: 1 Card Name (SET) CollectorNumber
    """
    name = card.get("name")
    set_code = card.get("set_code")
    collector_number = card.get("collector_number")

    if not name:
        return ""

    if set_code and collector_number:
        return f"{quantity} {name} ({set_code.upper()}) {collector_number}"
    
    return f"{quantity} {name}"


def export_deck_to_moxfield(deck_cards: List[Dict[str, Any]], output_path: Path) -> Path:
    """
    Exports a list of card dictionaries to a Moxfield-compatible text file.
    """
    lines = []
    for card in deck_cards:
        # Assuming quantity 1 for now, as is typical for Commander unless basic lands
        # For a more robust implementation, 'quantity' could be part of the card dict
        quantity = card.get("quantity", 1)
        line = export_moxfield_line(card, quantity)
        if line:
            lines.append(line)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return output_path
