import sqlite3
import json
from functools import lru_cache
from pathlib import Path
from typing import List, Dict, Any, Optional


@lru_cache(maxsize=1)
def _commander_overrides() -> frozenset:
    """Names that ARE legal commanders despite failing the can_be_commander heuristic
    (non-creature face commanders with no detectable oracle signal). Curated allowlist."""
    try:
        from mtgcli.config import SEED_DATA_DIR
        path = SEED_DATA_DIR / "commander_overrides.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return frozenset(data.get("commanders", []))
    except Exception:
        pass
    return frozenset()


def row_to_card(row: sqlite3.Row) -> Dict[str, Any]:
    """Converts a SQLite row into a card dictionary, parsing JSON fields."""
    card = dict(row)

    json_fields = ["colors", "color_identity", "games", "finishes"]
    for field in json_fields:
        if field in card and card[field]:
            card[field] = json.loads(card[field])
        else:
            card[field] = []

    card["commander_legal"] = bool(card["commander_legal"])
    card["can_be_commander"] = bool(card["can_be_commander"])
    # Apply curated allowlist for commanders the heuristic can't detect (e.g. Legendary
    # Vehicles printed as face commanders). Read-time override so the DB needn't be rebuilt.
    if not card["can_be_commander"] and card.get("name") in _commander_overrides():
        card["can_be_commander"] = True
    card["digital"] = bool(card["digital"])

    # Guarantee P/T keys exist even on databases built before the schema added
    # them. Values stay null until the user rebuilds local data.
    card.setdefault("power", None)
    card.setdefault("toughness", None)

    return card


class CardRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_card_by_exact_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Performs a case-insensitive exact name lookup.

        Falls back to matching the front face of double-faced / split cards, whose
        stored name is "Front // Back" (e.g. a lookup for "Valakut Awakening"
        resolves "Valakut Awakening // Valakut Stoneforge").
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM cards WHERE name = ? COLLATE NOCASE",
                (name,)
            )
            row = cursor.fetchone()
            if row:
                return row_to_card(row)

            # Fallback: front-face match for double-faced/split cards.
            if "//" not in name:
                cursor.execute(
                    "SELECT * FROM cards WHERE name LIKE ? COLLATE NOCASE",
                    (f"{name} // %",)
                )
                row = cursor.fetchone()
                if row:
                    return row_to_card(row)

            return None

    def search_cards_by_name(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Searches for cards with names containing the query string."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM cards WHERE name LIKE ? LIMIT ?",
                (f"%{query}%", limit)
            )
            rows = cursor.fetchall()
            return [row_to_card(row) for row in rows]

    def suggest_similar_names(self, name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Name suggestions for a not-found card.

        Substring match first (cheap, covers partial names); when that finds
        nothing, falls back to fuzzy matching over all card names so in-word
        typos still suggest ("Krenkooo" -> "Krenko, Mob Boss", "Sol Rign" ->
        "Sol Ring"). Cutoff 0.6 measured against the real DB: resolves
        common misspellings without surfacing junk. Only the "name" key is
        guaranteed on fallback results — this is an error-path helper, not a
        card lookup.
        """
        matches = self.search_cards_by_name(name, limit=limit)
        if matches:
            return matches
        import difflib
        with self._get_connection() as conn:
            all_names = [r[0] for r in conn.execute("SELECT name FROM cards")]
        by_lower: Dict[str, str] = {}
        for n in all_names:
            by_lower.setdefault(n.lower(), n)
        close = difflib.get_close_matches(name.lower(), list(by_lower), n=limit, cutoff=0.6)
        return [{"name": by_lower[c]} for c in close]
