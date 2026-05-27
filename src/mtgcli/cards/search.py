import sqlite3
import json
from typing import List, Dict, Any, Optional
from mtgcli.config import SQLITE_PATH, SEED_DATA_DIR
from mtgcli.cards.repository import row_to_card


def dedupe_cards(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicates a list of cards by oracle_id (or name), keeping the best printing.
    Priority: Physical > Has Set/Collector # > Has Price > First Seen.
    """
    best_prints = {}

    for card in cards:
        # 1. Identify identity
        identity = card.get("oracle_id") or card.get("name", "").lower()
        if not identity:
            continue

        if identity not in best_prints:
            best_prints[identity] = card
            continue

        current_best = best_prints[identity]

        # 2. Compare priority
        # Priority criteria (lower index is better)
        # 1. digital is False
        # 2. has set_code and collector_number
        # 3. has usd_price

        def get_priority_score(c):
            score = 0
            if c.get("digital"):
                score += 4
            if not (c.get("set_code") and c.get("collector_number")):
                score += 2
            if not c.get("usd_price"):
                score += 1
            return score

        if get_priority_score(card) < get_priority_score(current_best):
            best_prints[identity] = card

    return list(best_prints.values())


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
    seen_ids = set()
    
    # Normalize requested colors to a set for comparison
    allowed_colors = set(colors.upper()) if colors else None

    for row in cursor:
        card = row_to_card(row)
        
        # Deduplicate by oracle_id, fallback to lowercased name
        dedup_id = card.get("oracle_id") or card["name"].lower()
        if dedup_id in seen_ids:
            continue

        # Color Identity Filtering
        if allowed_colors is not None:
            card_identity = set(card.get("color_identity", []))
            # If card identity is not a subset of allowed colors, skip it
            if not card_identity.issubset(allowed_colors):
                continue
        
        results.append(card)
        seen_ids.add(dedup_id)
        
        # Apply limit after color filtering
        if len(results) >= limit:
            break

    conn.close()
    return results


def search_by_tags(
    tags: List[str],
    colors: Optional[str] = None,
    limit: int = 50,
    max_price: Optional[float] = None,
    exclude_names: Optional[List[str]] = None,
    dedupe: bool = True
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
        # Check for direct tag match
        if tag in tag_definitions:
            search_phrases.extend(tag_definitions[tag])
        else:
            # If not in definitions, use the tag itself as a search phrase (e.g. for themes like 'goblins')
            search_phrases.append(tag)

    if not search_phrases:
        return []

    if not SQLITE_PATH.exists():
        return []

    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Build the OR query for all phrases
    # Only return commander_legal cards
    sql = "SELECT * FROM cards WHERE commander_legal = 1"
    params = []

    # Price filter
    if max_price is not None:
        sql += " AND (usd_price <= ? OR usd_price IS NULL)"
        params.append(max_price)

    # Exclusions
    if exclude_names:
        placeholders = ",".join(["?"] * len(exclude_names))
        sql += f" AND name NOT IN ({placeholders}) COLLATE NOCASE"
        params.extend(exclude_names)

    sql += " AND ("
    phrase_conditions = []
    for phrase in search_phrases:
        phrase_conditions.append("(name LIKE ? OR type_line LIKE ? OR oracle_text LIKE ?)")
        like_query = f"%{phrase}%"
        params.extend([like_query, like_query, like_query])
    
    sql += " OR ".join(phrase_conditions) + ")"
    
    cursor.execute(sql, params)
    
    results = []
    seen_ids = set()
    allowed_colors = set(colors.upper()) if colors else None

    for row in cursor:
        card = row_to_card(row)
        
        # Deduplicate by oracle_id, fallback to lowercased name
        if dedupe:
            dedup_id = card.get("oracle_id") or card["name"].lower()
            if dedup_id in seen_ids:
                continue
            
        # Color Identity Filtering
        if allowed_colors is not None:
            card_identity = set(card.get("color_identity", []))
            if not card_identity.issubset(allowed_colors):
                continue
        
        results.append(card)
        if dedupe:
            seen_ids.add(dedup_id)
        
        if len(results) >= limit:
            break

    conn.close()
    return results
