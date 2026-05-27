import sqlite3
import json
import ijson
from pathlib import Path
from typing import List, Dict, Any

from mtgcli.config import RAW_CARDS_PATH, SQLITE_PATH
from mtgcli.data.normalize_cards import normalize_card

# Read and normalize cards using ijson for streaming
CHUNK_SIZE = 1000

def build_sqlite_database() -> Path:
    """
    Reads raw Scryfall cards, normalizes them, and builds a SQLite database.
    """
    if not RAW_CARDS_PATH.exists():
        raise FileNotFoundError(f"Raw cards file not found at {RAW_CARDS_PATH}")

    # Ensure processed directory exists
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Connect to (or create) the database
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()

    # Create the table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cards (
        scryfall_id TEXT PRIMARY KEY,
        oracle_id TEXT,
        name TEXT NOT NULL,
        set_code TEXT,
        collector_number TEXT,
        mana_cost TEXT,
        mana_value REAL,
        type_line TEXT,
        oracle_text TEXT,
        colors TEXT,
        color_identity TEXT,
        commander_legal INTEGER,
        can_be_commander INTEGER,
        rarity TEXT,
        usd_price REAL,
        layout TEXT,
        games TEXT,
        digital INTEGER,
        finishes TEXT
    );
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_oracle_id ON cards(oracle_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_commander_legal ON cards(commander_legal);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_can_be_commander ON cards(can_be_commander);")

    insert_sql = """
    INSERT OR REPLACE INTO cards (
        scryfall_id, oracle_id, name, set_code, collector_number,
        mana_cost, mana_value, type_line, oracle_text,
        colors, color_identity, commander_legal, can_be_commander,
        rarity, usd_price, layout, games, digital, finishes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    with open(RAW_CARDS_PATH, "rb") as f:
        # ijson.items streams objects from the root array
        parser = ijson.items(f, 'item')
        
        chunk = []
        for raw_card in parser:
            norm = normalize_card(raw_card)
            
            # Prepare the tuple for SQL insertion
            chunk.append((
                norm["scryfall_id"],
                norm["oracle_id"],
                norm["name"],
                norm["set_code"],
                norm["collector_number"],
                norm["mana_cost"],
                float(norm["mana_value"]),
                norm["type_line"],
                norm["oracle_text"],
                json.dumps(norm["colors"]),
                json.dumps(norm["color_identity"]),
                1 if norm["commander_legal"] else 0,
                1 if norm["can_be_commander"] else 0,
                norm["rarity"],
                float(norm["usd_price"]) if norm["usd_price"] is not None else None,
                norm["layout"],
                json.dumps(norm["games"]),
                1 if norm["digital"] else 0,
                json.dumps(norm["finishes"])
            ))

            if len(chunk) >= CHUNK_SIZE:
                cursor.executemany(insert_sql, chunk)
                conn.commit()
                chunk = []
        
        # Insert remaining cards
        if chunk:
            cursor.executemany(insert_sql, chunk)
            conn.commit()

    conn.close()

    return SQLITE_PATH
