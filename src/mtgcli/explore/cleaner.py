import re
import json
from typing import Dict, List, Optional


_SECTION_MAP = {
    "High Synergy Cards": "high_synergy",
    "Top Cards": "top_cards",
}
_PRICE_RE = re.compile(r'^\$\d+\.\d{2}$')
_CARDVIEW_RE = re.compile(r'"cardviews":(\[.*?\]),"header":"(.*?)"')

# ASCII control characters (incl. DEL) that break strict JSON parsing.
CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")


def sanitize_json_string(value: Optional[str]) -> Optional[str]:
    """Strip ASCII control characters and collapse whitespace.

    Defends against control characters leaking into JSON payloads (card names,
    URLs, notes) so strict ``json.loads()`` can always parse the output.
    """
    if value is None:
        return value
    value = CONTROL_CHAR_RE.sub(" ", str(value))
    value = re.sub(r"\s+", " ", value).strip()
    return value


def extract_target_cards_from_html(html_content: str) -> Dict[str, List[str]]:
    """Parses EDHREC HTML and extracts High Synergy and Top Cards sections."""
    results: Dict[str, List[str]] = {"high_synergy": [], "top_cards": []}

    for match in _CARDVIEW_RE.finditer(html_content):
        section_name = match.group(2)
        if section_name not in _SECTION_MAP:
            continue
        target_key = _SECTION_MAP[section_name]
        try:
            cards = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        for card in cards:
            name = sanitize_json_string(card.get("name") or "")
            if name and not _PRICE_RE.match(name) and name not in results[target_key]:
                results[target_key].append(name)

    return results
