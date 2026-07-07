"""Building notes — the carpenter's tally (user design, 2026-07-06).

The agent RECORDS findings during a build instead of holding them in memory:
combos spotted while drafting, decisions made, frictions found. `mtg note` writes
them; `mtg deck-power` reads the combo notes as first-class combo sources beside
the external fetch.

Storage: output/build-notes.json (a build artifact — cleared by temp-clean like the
rest of output/, and meant to be copied into the final-build folder so the deck
ships with its notebook).

Note shape:
    {"seq": 1, "timestamp": "...", "type": "combo|finding|decision",
     "text": "...", "cards": ["A", "B"], "combo_class": "infinite|non_infinite|utility|auto_win"}
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from mtgcli.config import OUTPUT_DIR

NOTES_PATH = OUTPUT_DIR / "build-notes.json"

NOTE_TYPES = ("combo", "finding", "decision")
COMBO_CLASSES = ("infinite", "non_infinite", "utility", "auto_win")


def load_notes(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    p = path or NOTES_PATH
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("notes", []) if isinstance(data, dict) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_notes(notes: List[Dict[str, Any]], path: Optional[Path] = None) -> None:
    p = path or NOTES_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"notes": notes}, indent=2, ensure_ascii=False) + "\n",
                 encoding="utf-8")


def add_note(text: str, note_type: str = "finding",
             cards: Optional[List[str]] = None, combo_class: Optional[str] = None,
             path: Optional[Path] = None) -> Dict[str, Any]:
    notes = load_notes(path)
    entry: Dict[str, Any] = {
        "seq": (notes[-1]["seq"] + 1) if notes else 1,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "type": note_type,
        "text": text,
    }
    if cards:
        entry["cards"] = cards
    if combo_class:
        entry["combo_class"] = combo_class
    notes.append(entry)
    save_notes(notes, path)
    return entry


def combo_notes(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """The combo-typed notes — deck-power's agent-observed combo source."""
    return [n for n in load_notes(path) if n.get("type") == "combo" and n.get("cards")]
