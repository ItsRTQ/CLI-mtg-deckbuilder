"""The user's card collection ("user bulk") — cards the user already OWNS.

Purpose: owned cards cost the budget $0. The collection tracks OWNERSHIP, not
quantity — a Commander deck is singleton and basics are unlimited, so owning a card
simply means every copy of it in a deck is free (no per-copy counting).

`mtg bulk-add` maintains the collection in TWO synced forms:
`user-bulk/collection.txt` (a plain name-per-line list, hand-editable — a leading
"N " quantity is tolerated but ignored, `#` comments allowed) and
`user-bulk/collection.json` (structured, easier for the agent to read). Every save
writes both; the `.txt` is the canonical hand-editable source (the loader reads it
first and falls back to the `.json`).

DEFAULT_OWNED: even with an empty collection, everyone is assumed to own the five
basic lands, Sol Ring, and Arcane Signet — these are always treated as free by the
budget (see owned_lookup).

Matching is case-insensitive by card name: deck entries carry canonical DB names,
manual bulk entries may not — lowercase comparison bridges them.
"""
import json
import re
from pathlib import Path
from typing import Dict, Iterable, Set

from mtgcli.config import USER_BULK_FILE

_LINE_RE = re.compile(r"^(?:(\d+)[xX]?\s+)?(.+?)\s*$")

# Assumed-owned by default (free for the budget) even if the collection is empty.
DEFAULT_OWNED = ("Plains", "Island", "Swamp", "Mountain", "Forest",
                 "Sol Ring", "Arcane Signet")


def _owned_to_payload(owned: Dict[str, int]) -> dict:
    names = sorted(owned, key=str.lower)
    return {
        "_doc": ("The user's owned cards (user-bulk) — OWNERSHIP, not quantity. Owned "
                 "cards cost a deck's budget $0 (all copies). Maintained by `mtg bulk-add`; "
                 "the hand-editable source is collection.txt. Plus the always-assumed "
                 "defaults: 5 basics, Sol Ring, Arcane Signet."),
        "count": len(names),
        "cards": names,
    }


def load_user_bulk(path: Path = None) -> Dict[str, int]:
    """name -> 1 (PRESENCE; quantity is not tracked). Reads the .txt (canonical); if it's
    missing, falls back to collection.json. Missing/empty -> {}. Does NOT inject the
    DEFAULT_OWNED staples (those live in owned_lookup, so the file stays user-authored)."""
    path = Path(path) if path else USER_BULK_FILE
    owned: Dict[str, int] = {}
    if not path.exists():
        return _load_json(path.with_suffix(".json"))  # sibling json fallback
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        owned[m.group(2)] = 1  # presence — any leading quantity is ignored
    return owned


def _load_json(json_path: Path) -> Dict[str, int]:
    if not json_path.exists():
        return {}
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    owned: Dict[str, int] = {}
    for c in data.get("cards", []):
        name = c if isinstance(c, str) else c.get("name")  # new (str) or old ({name,qty})
        if name:
            owned[name] = 1
    return owned


def save_user_bulk(owned: Iterable[str], path: Path = None,
                   json_path: Path = None) -> None:
    """Write the collection in BOTH forms: a plain name-per-line list (.txt, alphabetical,
    NO quantities) and a structured .json (agent-friendly). The json is written as the txt's
    sibling (`<stem>.json`) unless `json_path` is given."""
    names = {n for n in owned}
    path = Path(path) if path else USER_BULK_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = sorted(names, key=str.lower)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    payload = _owned_to_payload({n: 1 for n in names})
    jpath = Path(json_path) if json_path else path.with_suffix(".json")
    jpath.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")


def owned_lookup(owned: Iterable[str], include_defaults: bool = True) -> Set[str]:
    """Lowercased owned-name SET for matching deck entries, PLUS the always-assumed
    DEFAULT_OWNED staples (5 basics + Sol Ring + Arcane Signet) unless include_defaults
    is False. Presence-based: an owned card is free for ALL its copies."""
    names = {n.lower() for n in owned}
    if include_defaults:
        names |= {n.lower() for n in DEFAULT_OWNED}
    return names
