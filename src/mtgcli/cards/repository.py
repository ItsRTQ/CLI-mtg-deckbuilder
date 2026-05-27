import sqlite3
import json
from typing import List, Dict, Any, Optional


def row_to_card(row: sqlite3.Row) -> Dict[str, Any]:
    """Converts a SQLite row into a card dictionary, parsing JSON fields."""
    card = dict(row)
    
    # Fields stored as JSON strings in SQLite
    json_fields = ["colors", "color_identity", "games", "finishes"]
    for field in json_fields:
        if field in card and card[field]:
            card[field] = json.loads(card[field])
        else:
            card[field] = []
            
    # Boolean conversions (stored as 0/1 in SQLite)
    card["commander_legal"] = bool(card["commander_legal"])
    card["can_be_commander"] = bool(card["can_be_commander"])
    card["digital"] = bool(card["digital"])
    
    return card


class CardRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_card_by_exact_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Performs a case-insensitive exact name lookup."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM cards WHERE name = ? COLLATE NOCASE",
                (name,)
            )
            row = cursor.fetchone()
            return row_to_card(row) if row else None

    def get_card_by_exact_match(
        self, 
        name: str, 
        set_code: Optional[str] = None, 
        collector_number: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Tries to find a card by name, set_code, and collector_number.
        If set_code and collector_number are not provided, or no match is found,
        it falls back to get_card_by_exact_name (case-insensitive).
        """
        if set_code and collector_number:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM cards WHERE name = ? COLLATE NOCASE AND set_code = ? AND collector_number = ?",
                    (name, set_code, str(collector_number))
                )
                row = cursor.fetchone()
                if row:
                    return row_to_card(row)
        
        return self.get_card_by_exact_name(name)

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
