"""The user's card collection ("user bulk") — cards the user already OWNS.

Purpose: owned cards cost the budget $0. `mtg bulk-add` maintains the file
through the tool (names validated against the DB); the user may also edit it
by hand — `user-bulk/collection.txt` is a plain decklist ("2 Sol Ring" or
"Sol Ring" per line, `#` comments allowed), so the loader is tolerant.

Matching is case-insensitive by card name: deck entries carry canonical DB
names, manual bulk entries may not — lowercase comparison bridges them.
"""
import re
from pathlib import Path
from typing import Dict

from mtgcli.config import USER_BULK_FILE

_LINE_RE = re.compile(r"^(?:(\d+)[xX]?\s+)?(.+?)\s*$")


def load_user_bulk(path: Path = None) -> Dict[str, int]:
    """name -> owned quantity. Missing/empty file -> {}. Repeated names merge."""
    path = Path(path) if path else USER_BULK_FILE
    owned: Dict[str, int] = {}
    if not path.exists():
        return owned
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        qty = int(m.group(1)) if m.group(1) else 1
        name = m.group(2)
        owned[name] = owned.get(name, 0) + qty
    return owned


def save_user_bulk(owned: Dict[str, int], path: Path = None) -> None:
    """Write the collection back as a plain decklist, alphabetical."""
    path = Path(path) if path else USER_BULK_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{qty} {name}" for name, qty in sorted(owned.items(), key=lambda kv: kv[0].lower())
             if qty > 0]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def owned_lookup(owned: Dict[str, int]) -> Dict[str, int]:
    """Case-insensitive view (lowercase name -> qty) for matching deck entries."""
    out: Dict[str, int] = {}
    for name, qty in owned.items():
        key = name.lower()
        out[key] = out.get(key, 0) + qty
    return out
