"""Card-database refresh service — the code path behind the GUI's
"Download DB" / "Reload DB" button (and the init-data / update-data commands).

- download mode (no DB yet): download the Scryfall bulk if missing, build SQLite.
- full mode ("Reload DB"): DELETE raw + processed data (keeping .gitkeep), then
  re-download ~2GB and rebuild — the update-data behavior.
"""
from typing import Any, Callable, Dict, Optional

from mtgcli.config import PROCESSED_DATA_DIR, RAW_CARDS_PATH, RAW_DATA_DIR


def refresh_data(*, full: bool,
                 on_phase: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """Blocking (run it in a worker thread). Returns the build summary."""
    from mtgcli.data.build_sqlite import build_sqlite_database
    from mtgcli.data.download_cards import download_default_cards

    phase = on_phase or (lambda _msg: None)
    deleted = 0
    if full:
        phase("deleting current data")
        for d in (RAW_DATA_DIR, PROCESSED_DATA_DIR):
            if not d.exists():
                continue
            for f in d.iterdir():
                if f.is_file() and f.name != ".gitkeep":
                    f.unlink()
                    deleted += 1

    downloaded = False
    if not RAW_CARDS_PATH.exists():
        phase("downloading Scryfall bulk (~2GB — this takes a while)")
        download_default_cards()
        downloaded = True

    phase("building the card database")
    result = build_sqlite_database()
    return {"deleted_files": deleted, "downloaded": downloaded, "build": result}
