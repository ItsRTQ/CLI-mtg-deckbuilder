"""Preferred-printing store — the GUI's "switch print" persistence.

The card DB keeps ONE printing per card identity; when the user picks another
printing's art in the GUI, the choice lands as a name-keyed preference. Two
layers, resolved deck-first:

- DECK layer: the `print_prefs` key inside a library deck's deck_list.json —
  a print chosen while zooming inside a deck panel applies to that deck only.
- GLOBAL layer: data/gui_prints.json (gitignored — personal taste, like
  gui_settings) — the Collection/bulk store and the fallback for deck cards.

Both layers share the same `{name_lower: pref}` shape, so a future source
(e.g. a per-printing SQLite table) is just another layer for `resolve_pref`.
"""
import json
from pathlib import Path
from typing import Any, Dict, Optional

from mtgcli.config import DATA_DIR

GUI_PRINTS_PATH = DATA_DIR / "gui_prints.json"

_PREF_FIELDS = ("set", "collector_number", "image_url", "rarity")


def _clean_pref(pref: Dict[str, Any]) -> Dict[str, Any]:
    if not pref.get("image_url"):
        raise ValueError("A print preference needs an image_url.")
    return {k: pref.get(k) for k in _PREF_FIELDS}


def resolve_pref(name: str,
                 *layers: Optional[Dict[str, Dict[str, Any]]]) -> Dict[str, Any]:
    """First layer holding a pref for `name` wins (deck → global); {} if none."""
    key = name.lower()
    for layer in layers:
        pref = (layer or {}).get(key)
        if pref:
            return pref
    return {}


# ── Global layer (data/gui_prints.json) ───────────────────────────────────────

def load_print_prefs(*, path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    p = path or GUI_PRINTS_PATH
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def set_print_pref(name: str, pref: Dict[str, Any], *,
                   path: Optional[Path] = None) -> Dict[str, Any]:
    clean = _clean_pref(pref)
    p = path or GUI_PRINTS_PATH
    prefs = load_print_prefs(path=p)
    prefs[name.lower()] = clean
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(prefs, indent=2, ensure_ascii=False) + "\n",
                 encoding="utf-8")
    return clean


def clear_print_pref(name: str, *, path: Optional[Path] = None) -> bool:
    p = path or GUI_PRINTS_PATH
    prefs = load_print_prefs(path=p)
    if name.lower() not in prefs:
        return False
    del prefs[name.lower()]
    p.write_text(json.dumps(prefs, indent=2, ensure_ascii=False) + "\n",
                 encoding="utf-8")
    return True


# ── Deck layer (the `print_prefs` key of a deck_list.json) ────────────────────
# Surgical read-modify-write of the raw JSON: never goes through Deck.load/save
# (a cosmetic art change must not regen the .txt, rename the folder, or fail on
# a legacy deck the model's guards reject).

def load_deck_print_prefs(deck_list_path: Path) -> Dict[str, Dict[str, Any]]:
    try:
        data = json.loads(Path(deck_list_path).read_text(encoding="utf-8"))
        prefs = data.get("print_prefs") if isinstance(data, dict) else None
        return prefs if isinstance(prefs, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _rewrite_deck_prefs(deck_list_path: Path, mutate) -> Any:
    p = Path(deck_list_path)
    data = json.loads(p.read_text(encoding="utf-8"))
    prefs = data.get("print_prefs")
    if not isinstance(prefs, dict):
        prefs = {}
    result = mutate(prefs)
    if prefs:
        data["print_prefs"] = prefs
    else:
        data.pop("print_prefs", None)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                 encoding="utf-8")
    return result


def set_deck_print_pref(deck_list_path: Path, name: str,
                        pref: Dict[str, Any]) -> Dict[str, Any]:
    """Save a deck-scoped pref. ValueError on missing image_url; OSError /
    JSONDecodeError bubble to the caller (the endpoint 422s them)."""
    clean = _clean_pref(pref)

    def _set(prefs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        prefs[name.lower()] = clean
        return clean

    return _rewrite_deck_prefs(deck_list_path, _set)


def clear_deck_print_pref(deck_list_path: Path, name: str) -> bool:
    def _clear(prefs: Dict[str, Dict[str, Any]]) -> bool:
        return prefs.pop(name.lower(), None) is not None

    return _rewrite_deck_prefs(deck_list_path, _clear)


def preferred_image(name: str, default: Optional[str],
                    prefs: Optional[Dict[str, Dict[str, Any]]] = None) -> Optional[str]:
    """The user's chosen printing image for a card, else the DB default."""
    prefs = load_print_prefs() if prefs is None else prefs
    return resolve_pref(name, prefs).get("image_url") or default
