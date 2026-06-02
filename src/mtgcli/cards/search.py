import sqlite3
import json
from typing import List, Dict, Any, Optional
from mtgcli.config import SQLITE_PATH, SEED_DATA_DIR
from mtgcli.cards.repository import row_to_card
from mtgcli.cards.query_parser import (
    parse_search_query,
    build_search_conditions,
    check_query_conflicts,
    merge_parsed,
    empty_parsed,
)


# Broad card types matched against type_line via LOWER(type_line) LIKE.
BASIC_TYPE_FILTERS = [
    "artifact",
    "creature",
    "enchantment",
    "instant",
    "sorcery",
    "planeswalker",
    "land",
    "battle",
]

# Plural / common aliases normalized to a basic type.
_TYPE_ALIASES = {
    "artifacts": "artifact",
    "creatures": "creature",
    "enchantments": "enchantment",
    "instants": "instant",
    "sorceries": "sorcery",
    "planeswalkers": "planeswalker",
    "lands": "land",
    "battles": "battle",
}

# Compound aliases that expand to multiple basic types or a negation.
COMPOUND_TYPE_ALIASES = ["spell", "permanent", "nonland"]


class UnknownTypeFilterError(ValueError):
    """Raised when --type is given an unsupported value."""


def normalize_type_filter(value: str) -> str:
    """
    Normalizes a --type value to a canonical token.

    Returns one of BASIC_TYPE_FILTERS or COMPOUND_TYPE_ALIASES.
    Raises UnknownTypeFilterError for unsupported values.
    """
    token = (value or "").strip().lower()
    if not token:
        raise UnknownTypeFilterError(value)
    if token in BASIC_TYPE_FILTERS or token in COMPOUND_TYPE_ALIASES:
        return token
    if token in _TYPE_ALIASES:
        return _TYPE_ALIASES[token]
    raise UnknownTypeFilterError(value)


def build_type_filter_clause(value: str) -> tuple[str, List[str]]:
    """
    Builds a parameterized SQL condition (without leading AND) and params
    for a normalized --type value. Raises UnknownTypeFilterError if invalid.
    """
    canonical = normalize_type_filter(value)

    if canonical == "spell":
        return (
            "(LOWER(type_line) LIKE ? OR LOWER(type_line) LIKE ?)",
            ["%instant%", "%sorcery%"],
        )
    if canonical == "permanent":
        types = ["artifact", "creature", "enchantment", "planeswalker", "land", "battle"]
        clause = " OR ".join("LOWER(type_line) LIKE ?" for _ in types)
        return (f"({clause})", [f"%{t}%" for t in types])
    if canonical == "nonland":
        return ("LOWER(type_line) NOT LIKE ?", ["%land%"])

    return ("LOWER(type_line) LIKE ?", [f"%{canonical}%"])


def card_matches_type(card: Dict[str, Any], value: str) -> bool:
    """Python-side equivalent of build_type_filter_clause for post-filtering."""
    canonical = normalize_type_filter(value)
    type_line = (card.get("type_line") or "").lower()

    if canonical == "spell":
        return "instant" in type_line or "sorcery" in type_line
    if canonical == "permanent":
        return any(
            t in type_line
            for t in ("artifact", "creature", "enchantment", "planeswalker", "land", "battle")
        )
    if canonical == "nonland":
        return "land" not in type_line
    return canonical in type_line


def supported_types_message() -> str:
    """Human-readable list of supported --type values for error messages."""
    return (
        f"Supported types: {', '.join(BASIC_TYPE_FILTERS)}.\n"
        f"Aliases: {', '.join(COMPOUND_TYPE_ALIASES)} (plus plurals)."
    )


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
    limit: int = 50,
    type_filter: Optional[str] = None,
    extra_filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Searches for commander-legal cards with optional text and color identity filters.
    `type_filter` is a broad card-type filter (see normalize_type_filter).
    `extra_filters` is a parsed-query dict (see query_parser.empty_parsed) holding
    structured filters supplied via repeatable CLI options; it is AND-merged with
    the query string.
    """
    if not SQLITE_PATH.exists():
        return []

    # Parse the query string and AND-merge any CLI-supplied structured filters.
    # Validate before touching the DB so conflicting filters (e.g. mv>=5 mv<=2)
    # surface as a clean error, not silent [].
    parsed = parse_search_query(query) if query else None
    if extra_filters:
        parsed = merge_parsed(parsed or empty_parsed(), extra_filters)
    if parsed is not None:
        check_query_conflicts(parsed)

    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Base query
    sql = "SELECT * FROM cards WHERE commander_legal = 1"
    params = []

    # Structured token search — supports type:, oracle:, name:, mv: filters
    if parsed is not None:
        conditions, cond_params = build_search_conditions(parsed)
        for cond in conditions:
            sql += f" AND {cond}"
        params.extend(cond_params)

    # Broad --type filter on type_line (combines with type: tokens above)
    if type_filter:
        clause, clause_params = build_type_filter_clause(type_filter)
        sql += f" AND {clause}"
        params.extend(clause_params)

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
    dedupe: bool = True,
    type_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Searches for commander-legal cards matching specified tags.
    Tags may be direct card_tags keys, role names, or literal phrases.
    `type_filter` is a broad card-type filter (see normalize_type_filter).
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

    # Broad --type filter on type_line
    if type_filter:
        clause, clause_params = build_type_filter_clause(type_filter)
        sql += f" AND {clause}"
        params.extend(clause_params)

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
