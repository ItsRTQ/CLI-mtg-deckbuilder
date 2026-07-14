"""GUI settings service — small persistent key/value store for `mtg gui`.

Lives at data/gui_settings.json (gitignored — personal config). Settings:
- builds_save_dir: where SUCCEEDED GUI builds get saved as a named library folder
  (`<Commander>-<TIER>-<RANK>-<COST>`, the final-build convention). Defaults to
  the project's final-builds/ library; empty/None = keep builds only in their
  output/gui-builds/<job_id>/ workspace.
"""
import json
from pathlib import Path
from typing import Any, Dict, Optional

from mtgcli.config import DATA_DIR, FINAL_BUILDS_DIR, PROJECT_ROOT

GUI_SETTINGS_PATH = DATA_DIR / "gui_settings.json"

DEFAULTS: Dict[str, Any] = {
    "builds_save_dir": str(FINAL_BUILDS_DIR),
    # None = the project's user-bulk/ (a custom dir must contain collection.txt)
    "user_bulk_dir": None,
}


def load_gui_settings(*, path: Path = None) -> Dict[str, Any]:
    p = path or GUI_SETTINGS_PATH
    settings = dict(DEFAULTS)
    try:
        stored = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            settings.update(stored)
    except (OSError, json.JSONDecodeError):
        pass
    return settings


def save_gui_settings(settings: Dict[str, Any], *, path: Path = None) -> Dict[str, Any]:
    p = path or GUI_SETTINGS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    merged = load_gui_settings(path=p)
    merged.update(settings)
    p.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
                 encoding="utf-8")
    return merged


def resolve_save_dir(raw: Optional[str]) -> Optional[Path]:
    """Normalize the user's builds_save_dir: ~ expands, relative paths resolve
    against the project root, empty/None means 'don't save'. Raises ValueError
    if the path exists but is not a directory, or can't be created/written."""
    if raw is None or not str(raw).strip():
        return None
    p = Path(str(raw).strip()).expanduser()
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    if p.exists() and not p.is_dir():
        raise ValueError(f"Not a directory: {p}")
    try:
        p.mkdir(parents=True, exist_ok=True)
        probe = p / ".mtg-write-probe"
        probe.write_text("")
        probe.unlink()
    except OSError as e:
        raise ValueError(f"Folder is not writable: {p} ({e})")
    return p
