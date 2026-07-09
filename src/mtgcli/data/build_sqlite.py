import sqlite3
import json
import ijson
from pathlib import Path
from typing import Dict, Any

from mtgcli.config import RAW_CARDS_PATH, SQLITE_PATH
from mtgcli.data.normalize_cards import normalize_card, min_known_price, NONPLAYABLE_LAYOUTS

CHUNK_SIZE = 1000

_PRICE_FIELDS = [
    "usd_price", "usd_foil_price", "usd_etched_price", "edhrec_rank",
    "eur_price", "eur_foil_price", "tix_price",
]

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS cards (
    oracle_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    mana_cost TEXT,
    mana_value REAL,
    type_line TEXT,
    oracle_text TEXT,
    power TEXT,
    toughness TEXT,
    colors TEXT,
    color_identity TEXT,
    commander_legal INTEGER,
    can_be_commander INTEGER,
    usd_price REAL,
    edhrec_rank INTEGER,
    usd_foil_price REAL,
    usd_etched_price REAL,
    eur_price REAL,
    eur_foil_price REAL,
    tix_price REAL,
    price_status TEXT,
    price_source TEXT,
    layout TEXT,
    games TEXT,
    digital INTEGER,
    finishes TEXT,
    game_changer INTEGER,
    keywords TEXT,
    loyalty TEXT,
    produced_mana TEXT,
    all_parts TEXT,
    image_url TEXT
);
"""

_INSERT_SQL = """
INSERT OR REPLACE INTO cards (
    oracle_id, name, mana_cost, mana_value, type_line, oracle_text,
    power, toughness,
    colors, color_identity, commander_legal, can_be_commander,
    usd_price, usd_foil_price, usd_etched_price, edhrec_rank, eur_price, eur_foil_price, tix_price,
    price_status, price_source,
    layout, games, digital, finishes, game_changer,
    keywords, loyalty, produced_mana, all_parts, image_url
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _to_row(norm: Dict[str, Any]) -> tuple:
    return (
        norm["oracle_id"],
        norm["name"],
        norm["mana_cost"],
        float(norm["mana_value"]),
        norm["type_line"],
        norm["oracle_text"],
        norm["power"],
        norm["toughness"],
        json.dumps(norm["colors"]),
        json.dumps(norm["color_identity"]),
        1 if norm["commander_legal"] else 0,
        1 if norm["can_be_commander"] else 0,
        norm["usd_price"],
        norm["usd_foil_price"],
        norm["usd_etched_price"],
        norm.get("edhrec_rank"),
        norm["eur_price"],
        norm["eur_foil_price"],
        norm["tix_price"],
        norm["price_status"],
        norm["price_source"],
        norm["layout"],
        json.dumps(norm["games"]),
        1 if norm["digital"] else 0,
        json.dumps(norm["finishes"]),
        1 if norm.get("game_changer") else 0,
        json.dumps(norm.get("keywords") or []),
        norm.get("loyalty"),
        json.dumps(norm["produced_mana"]) if norm.get("produced_mana") is not None else None,
        json.dumps(norm["all_parts"]) if norm.get("all_parts") is not None else None,
        norm.get("image_url"),
    )


def build_sqlite_database() -> Dict[str, Any]:
    """
    Phase 1: stream all Scryfall printings, group by oracle_id, aggregate prices
             (min non-null) across every printing of the same card identity.
    Phase 2: write one merged row per card identity to SQLite.
    Returns counters dict including the SQLite path.
    """
    if not RAW_CARDS_PATH.exists():
        raise FileNotFoundError(f"Raw cards file not found at {RAW_CARDS_PATH}")

    # --- Phase 1: aggregate ---
    card_identities: Dict[str, Dict[str, Any]] = {}
    cards_processed = 0

    with open(RAW_CARDS_PATH, "rb") as f:
        for raw_card in ijson.items(f, "item"):
            # Tokens/emblems/art-series/etc. are not deck cards and token names SHADOW
            # real cards in exact-name lookups (the Timeless Witness bug).
            if (raw_card.get("layout") or "") in NONPLAYABLE_LAYOUTS:
                continue
            norm = normalize_card(raw_card)
            key = norm["oracle_id"]
            cards_processed += 1

            if key not in card_identities:
                card_identities[key] = norm
            else:
                existing = card_identities[key]
                for field in _PRICE_FIELDS:
                    existing[field] = min_known_price(existing[field], norm[field])
                # First-printing-wins leaves gaps for PER-PRINTING fields when the first
                # printing lacks them (image_url; defensively also the oracle-level
                # Fase-1 fields) — fill from any later printing that has a value.
                for field in ("image_url", "loyalty", "produced_mana", "all_parts"):
                    if existing.get(field) is None and norm.get(field) is not None:
                        existing[field] = norm[field]
                if not existing.get("keywords") and norm.get("keywords"):
                    existing["keywords"] = norm["keywords"]

    # Finalize price_status and price_source after all printings are merged
    cards_with_known_usd = 0
    cards_with_unknown_price = 0
    for card in card_identities.values():
        any_known = any(card.get(f) is not None for f in _PRICE_FIELDS)
        card["price_status"] = "known" if any_known else "unknown"
        card["price_source"] = "scryfall_aggregated_printings"
        if card.get("usd_price") is not None:
            cards_with_known_usd += 1
        else:
            cards_with_unknown_price += 1

    # --- Phase 2: write SQLite ---
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()

    cursor.execute(_CREATE_TABLE)
    # Migration guard: CREATE TABLE IF NOT EXISTS never alters an EXISTING table, so a
    # rebuild over an old DB crashed on any new column ("table cards has no column named
    # game_changer"). Diff the live schema against _CREATE_TABLE and ALTER in what's
    # missing — durable for every future column, no ad-hoc repair scripts.
    cursor.execute("PRAGMA table_info(cards)")
    _existing = {row[1] for row in cursor.fetchall()}
    for _line in _CREATE_TABLE.splitlines():
        _line = _line.strip().rstrip(",")
        if not _line or _line.startswith(("CREATE", ");", '"')) or _line == ");":
            continue
        _parts = _line.split()
        if len(_parts) >= 2 and _parts[0] not in _existing and _parts[0].isidentifier():
            cursor.execute(f"ALTER TABLE cards ADD COLUMN {_parts[0]} {_parts[1]}")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_commander_legal ON cards(commander_legal);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_can_be_commander ON cards(can_be_commander);")

    all_cards = list(card_identities.values())
    for i in range(0, len(all_cards), CHUNK_SIZE):
        chunk = [_to_row(c) for c in all_cards[i : i + CHUNK_SIZE]]
        cursor.executemany(_INSERT_SQL, chunk)
        conn.commit()

    conn.close()

    return {
        "path": str(SQLITE_PATH),
        "cards_processed": cards_processed,
        "unique_card_identities": len(card_identities),
        "cards_with_known_usd_price": cards_with_known_usd,
        "cards_with_unknown_price": cards_with_unknown_price,
        "price_aggregation_enabled": True,
    }
