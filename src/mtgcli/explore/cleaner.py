import re
import json
from typing import Dict, List


_SECTION_MAP = {
    "High Synergy Cards": "high_synergy",
    "Top Cards": "top_cards",
}
_PRICE_RE = re.compile(r'^\$\d+\.\d{2}$')
_CARDVIEW_RE = re.compile(r'"cardviews":(\[.*?\]),"header":"(.*?)"')


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
            name = (card.get("name") or "").strip()
            if name and not _PRICE_RE.match(name) and name not in results[target_key]:
                results[target_key].append(name)

    return results
