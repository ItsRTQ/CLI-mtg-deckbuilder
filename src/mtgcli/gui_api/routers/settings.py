"""GUI settings endpoints: where succeeded builds get saved, etc."""
import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# Module-attribute access ON PURPOSE (late binding): tests monkeypatch functions
# on mtgcli.core.gui_settings; a `from ... import name` here would capture
# whatever value happens to be live when this module first imports.
from mtgcli.core import gui_settings

router = APIRouter()


class SettingsOut(BaseModel):
    builds_save_dir: Optional[str] = None
    builds_save_dir_resolved: Optional[str] = None
    user_bulk_dir: Optional[str] = None
    user_bulk_dir_resolved: str = ""      # EFFECTIVE dir (custom or project default)


class SettingsIn(BaseModel):
    # Only fields the client actually SENDS are updated (model_fields_set).
    builds_save_dir: Optional[str] = None  # empty/None = don't save to a library
    user_bulk_dir: Optional[str] = None    # empty/None = the project's user-bulk/


def _out() -> SettingsOut:
    from mtgcli.deckbuilder.user_bulk import default_bulk_file

    s = gui_settings.load_gui_settings()
    raw = s.get("builds_save_dir")
    try:
        resolved = gui_settings.resolve_save_dir(raw)
    except ValueError:
        resolved = None
    return SettingsOut(
        builds_save_dir=raw,
        builds_save_dir_resolved=str(resolved) if resolved else None,
        user_bulk_dir=s.get("user_bulk_dir"),
        user_bulk_dir_resolved=str(default_bulk_file().parent),
    )


@router.get("/settings", response_model=SettingsOut)
def get_settings() -> SettingsOut:
    return _out()


class DirListOut(BaseModel):
    path: str
    parent: Optional[str] = None
    dirs: List[str] = []          # subdirectory NAMES (join with path to descend)
    writable: bool = True


@router.get("/settings/browse", response_model=DirListOut)
def browse_dirs(path: Optional[str] = Query(None,
                description="Directory to list; omit for the user's home")) -> DirListOut:
    """Server-side folder browser for the 'Browse…' picker: browsers can't reveal
    real filesystem paths, but this server RUNS on the user's machine — it lists
    directories so the UI can navigate and pick one."""
    p = Path(path).expanduser() if path and path.strip() else Path.home()
    try:
        p = p.resolve()
    except OSError:
        p = Path.home()
    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": f"Not a directory: {p}"}})
    try:
        dirs = sorted(
            (e.name for e in p.iterdir() if e.is_dir() and not e.name.startswith(".")),
            key=str.lower)
    except PermissionError:
        raise HTTPException(status_code=422, detail={"error": {
            "type": "validation", "message": f"Permission denied: {p}"}})
    return DirListOut(path=str(p),
                      parent=str(p.parent) if p.parent != p else None,
                      dirs=dirs,
                      writable=os.access(p, os.W_OK))


@router.post("/settings", response_model=SettingsOut)
def update_settings(body: SettingsIn) -> SettingsOut:
    updates = {}
    for key in ("builds_save_dir", "user_bulk_dir"):
        if key not in body.model_fields_set:
            continue  # not sent -> leave the stored value alone
        raw = (getattr(body, key) or "").strip() or None
        if raw is not None:
            try:
                gui_settings.resolve_save_dir(raw)  # dir-or-creatable + writable
            except ValueError as e:
                raise HTTPException(status_code=422, detail={"error": {
                    "type": "validation", "message": str(e)}})
        updates[key] = raw
    if updates:
        gui_settings.save_gui_settings(updates)
    return _out()
