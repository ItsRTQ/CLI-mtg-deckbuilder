import re
from typing import Dict, Any, List, Tuple, Optional


def parse_search_query(query: str) -> Dict[str, Any]:
    """
    Parses a search query string into structured token groups.

    Supported tokens:
      type:<value>   → match type_line
      oracle:<value> → match oracle_text
      text:<value>   → alias for oracle:
      name:<value>   → match name
      mv:<n>         → exact mana_value
      mv<=<n>        → mana_value ≤ n
      mv>=<n>        → mana_value ≥ n

    Unrecognized tokens are treated as free-text (match name/type/oracle).
    Multiple tokens of the same kind are AND'd together.
    """
    result: Dict[str, Any] = {
        "free_text": [],
        "type_terms": [],
        "oracle_terms": [],
        "name_terms": [],
        "mana_value_eq": None,
        "mana_value_lte": None,
        "mana_value_gte": None,
    }

    for raw_token in query.split():
        token = raw_token.strip()
        if not token:
            continue
        lower = token.lower()

        if lower.startswith("type:"):
            value = token[5:].lower()
            if value:
                result["type_terms"].append(value)
        elif lower.startswith("oracle:") or lower.startswith("text:"):
            prefix_len = 7 if lower.startswith("oracle:") else 5
            value = token[prefix_len:].lower()
            if value:
                result["oracle_terms"].append(value)
        elif lower.startswith("name:"):
            value = token[5:].lower()
            if value:
                result["name_terms"].append(value)
        elif lower.startswith("mv<="):
            try:
                result["mana_value_lte"] = float(token[4:])
            except ValueError:
                result["free_text"].append(token)
        elif lower.startswith("mv>="):
            try:
                result["mana_value_gte"] = float(token[4:])
            except ValueError:
                result["free_text"].append(token)
        elif re.match(r'^mv:[0-9]+(\.[0-9]+)?$', lower):
            try:
                result["mana_value_eq"] = float(token[3:])
            except ValueError:
                result["free_text"].append(token)
        else:
            result["free_text"].append(token)

    return result


def build_search_conditions(
    parsed: Dict[str, Any],
) -> Tuple[List[str], List[Any]]:
    """
    Converts a parsed query dict into (sql_conditions, params) to append to a WHERE clause.
    Each condition is a complete AND fragment (without the leading AND).
    """
    conditions: List[str] = []
    params: List[Any] = []

    for term in parsed["type_terms"]:
        conditions.append("type_line LIKE ?")
        params.append(f"%{term}%")

    for term in parsed["oracle_terms"]:
        conditions.append("oracle_text LIKE ?")
        params.append(f"%{term}%")

    for term in parsed["name_terms"]:
        conditions.append("name LIKE ?")
        params.append(f"%{term}%")

    for term in parsed["free_text"]:
        conditions.append("(name LIKE ? OR type_line LIKE ? OR oracle_text LIKE ?)")
        like = f"%{term}%"
        params.extend([like, like, like])

    if parsed["mana_value_eq"] is not None:
        conditions.append("mana_value = ?")
        params.append(parsed["mana_value_eq"])

    if parsed["mana_value_lte"] is not None:
        conditions.append("mana_value <= ?")
        params.append(parsed["mana_value_lte"])

    if parsed["mana_value_gte"] is not None:
        conditions.append("mana_value >= ?")
        params.append(parsed["mana_value_gte"])

    return conditions, params


def is_plain_query(query: str) -> bool:
    """Returns True if the query has no structured tokens (pure free text)."""
    parsed = parse_search_query(query)
    return (
        not parsed["type_terms"]
        and not parsed["oracle_terms"]
        and not parsed["name_terms"]
        and parsed["mana_value_eq"] is None
        and parsed["mana_value_lte"] is None
        and parsed["mana_value_gte"] is None
    )
