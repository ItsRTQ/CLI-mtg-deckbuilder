import re
from typing import List, Dict, Any


def parse_decklist_text(text: str) -> List[Dict[str, Any]]:
    """
    Parses a plain-text decklist into a list of {name, quantity} dicts.

    Supported line formats:
      1 Sol Ring
      1x Sol Ring
      1X Sol Ring
      Sol Ring          (quantity defaults to 1)
      # comment         (skipped)
      ## Section Header (skipped)
      (empty lines skipped)
    """
    entries: List[Dict[str, Any]] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()

        # Skip empty lines and comments/section headers
        if not line or line.startswith("#"):
            continue

        # Try "1 Card Name" or "1x Card Name" or "1X Card Name"
        match = re.match(r'^(\d+)[xX]?\s+(.+)$', line)
        if match:
            qty = int(match.group(1))
            name = match.group(2).strip()
        else:
            qty = 1
            name = line

        if name:
            entries.append({"name": name, "quantity": qty})

    return entries
