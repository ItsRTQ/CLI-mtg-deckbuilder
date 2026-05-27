import sqlite3
import json
from typing import List, Dict, Any, Optional
from mtgcli.config import SQLITE_PATH, SEED_DATA_DIR
from mtgcli.cards.repository import row_to_card


def search_commander_legal_cards(
    query: Optional[str] = None,
    colors: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Searches for commander-legal cards with optional text and color identity filters.
    """
    if not SQLITE_PATH.exists():
        return []

    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Base query
    sql = "SELECT * FROM cards WHERE commander_legal = 1"
    params = []

    # Text search (name, type_line, oracle_text)
    if query:
        sql += " AND (name LIKE ? OR type_line LIKE ? OR oracle_text LIKE ?)"
        like_query = f"%{query}%"
        params.extend([like_query, like_query, like_query])

    # Execute query
    cursor.execute(sql, params)
    
    # Process results with color filtering if needed
    results = []
    
    # Normalize requested colors to a set for comparison
    allowed_colors = set(colors.upper()) if colors else None

    for row in cursor:
        card = row_to_card(row)
        
        # Color Identity Filtering
        if allowed_colors is not None:
            card_identity = set(card.get("color_identity", []))
            # If card identity is not a subset of allowed colors, skip it
            if not card_identity.issubset(allowed_colors):
                continue
        
        results.append(card)
        
        # Apply limit after color filtering
        if len(results) >= limit:
            break

    conn.close()
    return results


def search_by_tags(
    tags: List[str],
    colors: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Searches for commander-legal cards matching specified tags.
    """
    tag_file = SEED_DATA_DIR / "card_tags.json"
    if not tag_file.exists():
        return []

    with open(tag_file, "r", encoding="utf-8") as f:
        tag_definitions = json.load(f)

    # Collect all phrases for the requested tags
    search_phrases = []
    for tag in tags:
        if tag in tag_definitions:
            search_phrases.extend(tag_definitions[tag])

    if not search_phrases:
        return []

    if not SQLITE_PATH.exists():
        return []

    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Build the OR query for all phrases
    # Only return commander_legal cards
    sql = "SELECT * FROM cards WHERE commander_legal = 1 AND ("
    phrase_conditions = []
    params = []
    for phrase in search_phrases:
        phrase_conditions.append("(name LIKE ? OR type_line LIKE ? OR oracle_text LIKE ?)")
        like_query = f"%{phrase}%"
        params.extend([like_query, like_query, like_query])
    
    sql += " OR ".join(phrase_conditions) + ")"
    
    cursor.execute(sql, params)
    
    results = []
    seen_names = set()
    allowed_colors = set(colors.upper()) if colors else None

    for row in cursor:
        card = row_to_card(row)
        
        # Deduplicate by name
        if card["name"] in seen_names:
            continue
            
        # Color Identity Filtering
        if allowed_colors is not None:
            card_identity = set(card.get("color_identity", []))
            if not card_identity.issubset(allowed_colors):
                continue
        
        results.append(card)
        seen_names.add(card["name"])
        
        if len(results) >= limit:
            break

    conn.close()
    return results
