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
from mtgcli.deckbuilder.ramp_rules import (
    MANA_RAMP_TAGS,
    RAMP_LAND_ALLOWED_TAGS,
    is_land,
    land_matches_allowed_ramp_tags,
    resolve_tag_keys,
)
from mtgcli.utils.phrase_match import phrase_matches, phrase_to_like


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



def search_by_trigger(
    family: str,
    colors: Optional[str] = None,
    type_filter: Optional[str] = None,
    max_mana_value: Optional[int] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Find commander-legal cards whose oracle text contains a trigger of the given event
    `family` (one of oracle_hooks' trigger families: permanent_dies, attacks_or_combat,
    you_cast_spell, etc.). A broad SQL prefilter on trigger words narrows the pool, then each
    candidate is classified with the same `extract_trigger_events` used for commander analysis."""
    from mtgcli.deckbuilder.oracle_hooks import extract_trigger_events
    if not SQLITE_PATH.exists():
        return []

    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    sql = ("SELECT * FROM cards WHERE commander_legal = 1 AND ("
           "LOWER(oracle_text) LIKE '%whenever%' OR LOWER(oracle_text) LIKE '%at the beginning%' "
           "OR LOWER(oracle_text) LIKE '% when %' OR LOWER(oracle_text) LIKE 'when %')")
    params: List[Any] = []
    if type_filter:
        clause, clause_params = build_type_filter_clause(type_filter)
        sql += f" AND {clause}"
        params.extend(clause_params)
    if max_mana_value is not None:
        sql += " AND mana_value <= ?"
        params.append(float(max_mana_value))

    cursor.execute(sql, params)
    allowed_colors = set(colors.upper()) if colors else None
    results: List[Dict[str, Any]] = []
    seen_ids = set()
    for row in cursor:
        card = row_to_card(row)
        dedup_id = card.get("oracle_id") or card["name"].lower()
        if dedup_id in seen_ids:
            continue
        if allowed_colors is not None and not set(card.get("color_identity", [])).issubset(allowed_colors):
            continue
        if family not in extract_trigger_events(card.get("oracle_text", "") or ""):
            continue
        results.append(card)
        seen_ids.add(dedup_id)
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
    type_filter: Optional[str] = None,
    rank: bool = False,
) -> List[Dict[str, Any]]:
    """
    Searches for commander-legal cards matching specified tags.
    Tags may be direct card_tags keys, role names, or literal phrases.
    `type_filter` is a broad card-type filter (see normalize_type_filter).

    Every result carries `tag_match_count` (how many of the requested tags' phrases it hits).
    When `rank=True`, results are sorted by that count (most on-function first) before the limit
    is applied; when False (default) results keep DB order with the limit applied as before, so
    existing callers like `suggest` are unaffected.
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
        # phrase_to_like maps the " * " qualifier wildcard to LIKE's % (recall-oriented;
        # the rank count below re-checks with the bounded same-clause gap).
        like_query = phrase_to_like(phrase)
        params.extend([like_query, like_query, like_query])
    
    sql += " OR ".join(phrase_conditions) + ")"
    
    cursor.execute(sql, params)
    
    results = []
    seen_ids = set()
    allowed_colors = set(colors.upper()) if colors else None

    # Land-ramp guard: when the search touches mana-production tags (mana_rock, etc.),
    # lands must qualify through an actually-requested land-oriented ramp tag — otherwise
    # every basic land leaks in via the mana_rock phrase "{T}: Add". Inactive for searches
    # that don't involve mana-production tags (e.g. landfall), so land-matters searches are
    # unaffected. Same rule deck_check and suggestion_scorer use, via the shared helper.
    resolved_keys = resolve_tag_keys(tags, tag_definitions, role_definitions)
    land_guard_active = bool(resolved_keys & MANA_RAMP_TAGS)
    allowed_land_tags = resolved_keys & RAMP_LAND_ALLOWED_TAGS

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

        # Drop lands that only leaked in via mana-production phrases.
        if land_guard_active and is_land(card) and not land_matches_allowed_ramp_tags(
            card, tag_definitions, allowed_land_tags
        ):
            continue

        # Rank signal: how many of the requested tags' phrases this card actually hits.
        text = " ".join([
            card.get("name", "") or "",
            card.get("type_line", "") or "",
            card.get("oracle_text", "") or "",
        ]).lower()
        card["tag_match_count"] = sum(1 for p in search_phrases if phrase_matches(p, text))
        results.append(card)
        if dedupe:
            seen_ids.add(dedup_id)

        # Default (unranked) path keeps DB order and stops at the limit, as before.
        if not rank and len(results) >= limit:
            break

    conn.close()
    if rank:
        def _popularity(c):
            # edhrec_rank: lower = more played (Sol Ring #1). NULL (digital-only / no EDHREC
            # data) sinks to the bottom of its tie group.
            r = c.get("edhrec_rank")
            return r if isinstance(r, int) else 10**9
        # Within the same tag-match count, prefer what Commander players actually play —
        # the definitive fix for the F3 chaff-flood (price proxy was the interim).
        results.sort(key=lambda c: (-c.get("tag_match_count", 0), _popularity(c), c.get("name", "")))
        return results[:limit]
    return results
