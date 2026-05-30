import sqlite3
import json
from typing import List, Dict, Any, Optional
from mtgcli.config import SQLITE_PATH, SEED_DATA_DIR
from mtgcli.cards.repository import row_to_card


def dedupe_cards(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicates a list of cards by oracle_id (or name).
    Prefers non-digital over digital when duplicates exist.
    """
    seen: Dict[str, Dict[str, Any]] = {}

    for card in cards:
        key = card.get("oracle_id") or card.get("name", "").lower()
        if not key:
            continue
        if key not in seen:
            seen[key] = card
        elif not card.get("digital") and seen[key].get("digital"):
            seen[key] = card

    return list(seen.values())


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


def _load_role_definitions() -> Dict[str, Any]:
    role_file = SEED_DATA_DIR / "role_definitions.json"
    if not role_file.exists():
        return {}
    with open(role_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _expand_tag_to_phrases(
    tag: str,
    tag_definitions: Dict[str, List[str]],
    role_definitions: Dict[str, Any],
) -> List[str]:
    """
    Returns search phrases for a tag.
    - Direct tag in card_tags.json → its phrase list
    - Role name in role_definitions → expand via sub-tags
    - Otherwise → use tag itself as a literal phrase (e.g. theme like 'goblins')
    """
    if tag in tag_definitions:
        return tag_definitions[tag]
    if tag in role_definitions:
        phrases = []
        for sub_tag in role_definitions[tag].get("tags", []):
            phrases.extend(tag_definitions.get(sub_tag, []))
        return phrases
    return [tag]


def search_by_tags(
    tags: List[str],
    colors: Optional[str] = None,
    limit: int = 50,
    max_price: Optional[float] = None,
    max_mana_value: Optional[int] = None,
    exclude_names: Optional[List[str]] = None,
    dedupe: bool = True
) -> List[Dict[str, Any]]:
    """
    Searches for commander-legal cards matching specified tags.
    Tags may be direct card_tags keys, role names, or literal phrases.
    """
    tag_file = SEED_DATA_DIR / "card_tags.json"
    if not tag_file.exists():
        return []

    with open(tag_file, "r", encoding="utf-8") as f:
        tag_definitions = json.load(f)

    role_definitions = _load_role_definitions()

    # Collect all phrases for the requested tags
    search_phrases = []
    for tag in tags:
        search_phrases.extend(_expand_tag_to_phrases(tag, tag_definitions, role_definitions))

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

    # Mana value filter
    if max_mana_value is not None:
        sql += " AND mana_value <= ?"
        params.append(float(max_mana_value))

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
