import sqlite3
import json
import ijson
from pathlib import Path
from typing import List, Dict, Any

from mtgcli.config import RAW_CARDS_PATH, SQLITE_PATH
from mtgcli.data.normalize_cards import normalize_card
from mtgcli.utils.json_io import safe_float

CHUNK_SIZE = 1000

def build_sqlite_database() -> Path:
    """
    Reads raw Scryfall cards, normalizes them, and builds a SQLite database.
    Deduplicates by oracle_id so each card identity appears exactly once.
    """
    if not RAW_CARDS_PATH.exists():
        raise FileNotFoundError(f"Raw cards file not found at {RAW_CARDS_PATH}")

    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cards (
        oracle_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        mana_cost TEXT,
        mana_value REAL,
        type_line TEXT,
        oracle_text TEXT,
        colors TEXT,
        color_identity TEXT,
        commander_legal INTEGER,
        can_be_commander INTEGER,
        usd_price REAL,
        layout TEXT,
        games TEXT,
        digital INTEGER,
        finishes TEXT
    );
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_commander_legal ON cards(commander_legal);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_can_be_commander ON cards(can_be_commander);")

    insert_sql = """
    INSERT OR IGNORE INTO cards (
        oracle_id, name, mana_cost, mana_value, type_line, oracle_text,
        colors, color_identity, commander_legal, can_be_commander,
        usd_price, layout, games, digital, finishes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    with open(RAW_CARDS_PATH, "rb") as f:
        parser = ijson.items(f, 'item')
        chunk = []
        for raw_card in parser:
            norm = normalize_card(raw_card)
            chunk.append((
                norm["oracle_id"],
                norm["name"],
                norm["mana_cost"],
                float(norm["mana_value"]),
                norm["type_line"],
                norm["oracle_text"],
                json.dumps(norm["colors"]),
                json.dumps(norm["color_identity"]),
                1 if norm["commander_legal"] else 0,
                1 if norm["can_be_commander"] else 0,
                safe_float(norm["usd_price"]),
                norm["layout"],
                json.dumps(norm["games"]),
                1 if norm["digital"] else 0,
                json.dumps(norm["finishes"])
            ))

            if len(chunk) >= CHUNK_SIZE:
                cursor.executemany(insert_sql, chunk)
                conn.commit()
                chunk = []

        if chunk:
            cursor.executemany(insert_sql, chunk)
            conn.commit()

    conn.close()
    return SQLITE_PATH
