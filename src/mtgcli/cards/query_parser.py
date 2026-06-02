import re
import shlex
from typing import Dict, Any, List, Tuple, Optional


class QueryConflictError(ValueError):
    """Raised when a search query contains mutually exclusive filters."""


def _tokenize(query: str) -> List[str]:
    """
    Splits a query into tokens, honoring quoted phrases so that
    `oracle:"draw a card"` becomes a single `oracle:draw a card` token.
    Falls back to plain whitespace splitting on unbalanced quotes.
    """
    try:
        return shlex.split(query)
    except ValueError:
        return query.split()


def empty_parsed() -> Dict[str, Any]:
    """Returns a fresh parsed-query dict with no filters set."""
    return {
        "free_text": [],
        "type_terms": [],
        "oracle_terms": [],
        "name_terms": [],
        "mana_value_eq": None,
        "mana_value_lte": None,
        "mana_value_gte": None,
    }


def merge_parsed(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merges two parsed-query dicts with AND semantics.

    List fields are concatenated. Mana-value bounds are combined to the most
    restrictive: smallest lte, largest gte. Equality must agree if set twice.
    """
    merged = empty_parsed()
    for key in ("free_text", "type_terms", "oracle_terms", "name_terms"):
        merged[key] = list(base.get(key, [])) + list(extra.get(key, []))

    def _pick(field, combine):
        a, b = base.get(field), extra.get(field)
        if a is None:
            return b
        if b is None:
            return a
        return combine(a, b)

    merged["mana_value_lte"] = _pick("mana_value_lte", min)
    merged["mana_value_gte"] = _pick("mana_value_gte", max)

    eq_a, eq_b = base.get("mana_value_eq"), extra.get("mana_value_eq")
    if eq_a is not None and eq_b is not None and eq_a != eq_b:
        raise QueryConflictError(
            f"Conflicting mana value filters: mv:{eq_a:g} and mv:{eq_b:g}."
        )
    merged["mana_value_eq"] = eq_a if eq_a is not None else eq_b

    return merged


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
    result: Dict[str, Any] = empty_parsed()

    for raw_token in _tokenize(query):
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


def check_query_conflicts(parsed: Dict[str, Any]) -> None:
    """
    Raises QueryConflictError if the parsed query has impossible filters,
    e.g. an empty mana-value range like `mv>=5 mv<=2`.
    """
    lte = parsed.get("mana_value_lte")
    gte = parsed.get("mana_value_gte")
    if lte is not None and gte is not None and gte > lte:
        raise QueryConflictError(
            f"Conflicting mana value filters: mv>={gte:g} and mv<={lte:g} "
            f"can never both be true."
        )

    eq = parsed.get("mana_value_eq")
    if eq is not None:
        if lte is not None and eq > lte:
            raise QueryConflictError(
                f"Conflicting mana value filters: mv:{eq:g} and mv<={lte:g}."
            )
        if gte is not None and eq < gte:
            raise QueryConflictError(
                f"Conflicting mana value filters: mv:{eq:g} and mv>={gte:g}."
            )


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
