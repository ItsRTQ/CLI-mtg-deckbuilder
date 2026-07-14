"""Project status service — the dict behind `mtg status` and GET /api/status."""
from pathlib import Path
from typing import Any, Dict

from mtgcli.config import PROJECT_ROOT, RAW_CARDS_PATH, SQLITE_PATH


def project_status(*, project_root: Path = PROJECT_ROOT,
                   sqlite_path: Path = SQLITE_PATH,
                   raw_cards_path: Path = RAW_CARDS_PATH) -> Dict[str, Any]:
    """Paths + existence flags for the project's data artifacts."""
    return {
        "project_root": str(project_root),
        "database_path": str(sqlite_path),
        "database_exists": sqlite_path.exists(),
        "raw_cards_path": str(raw_cards_path),
        "raw_cards_exists": raw_cards_path.exists(),
    }
