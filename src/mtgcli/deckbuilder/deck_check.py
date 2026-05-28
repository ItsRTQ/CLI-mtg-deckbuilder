import json
from typing import List, Dict, Any, Optional
from mtgcli.config import SEED_DATA_DIR
from mtgcli.cards.repository import CardRepository
from mtgcli.deckbuilder.theme_profiles import get_theme_packages

def check_theme_packages(deck_cards: List[Dict[str, Any]], theme: str) -> Dict[str, Any]:
    """
    Checks if the deck matches specific theme package requirements.
    """
    packages = get_theme_packages(theme)

    result = {
        "theme": theme,
        "package_counts": {},
        "warnings": []
    }

    for package_name, package_def in packages.items():
        search_phrases = package_def.get("search_phrases", [])
        minimum = package_def.get("min", 0)
        ideal = package_def.get("ideal", minimum)

        count = 0

        for card in deck_cards:
            quantity = card.get("quantity", 1)
            text = f"{card.get('name', '')} {card.get('type_line', '')} {card.get('oracle_text', '')}".lower()

            matched = False
            for phrase in search_phrases:
                if phrase.lower() in text:
                    matched = True
                    break

            if matched:
                count += quantity

        result["package_counts"][package_name] = {
            "count": count,
            "min": minimum,
            "ideal": ideal
        }

        if count < minimum:
            result["warnings"].append(
                f"Package '{package_name}' has {count} cards; recommended minimum is {minimum}."
            )

    return result

def check_deck_quality(deck_cards: List[Dict[str, Any]], theme: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyzes deck composition based on functional tags and optional thematic packages.
    """
    tag_file = SEED_DATA_DIR / "card_tags.json"
    tag_definitions = {}
    if tag_file.exists():
        with open(tag_file, "r", encoding="utf-8") as f:
            tag_definitions = json.load(f)

    stats = {
        "lands": 0,
        "ramp": 0,
        "card_draw": 0,
        "removal": 0,
        "board_wipe": 0,
        "protection": 0,
        "synergy": 0
    }
    
    core_categories = ["ramp", "card_draw", "removal", "board_wipe", "protection"]
    
    for card in deck_cards:
        name = card.get("name", "").lower()
        type_line = card.get("type_line", "").lower()
        oracle_text = card.get("oracle_text", "").lower()
        quantity = card.get("quantity", 1)
        
        if "land" in type_line:
            stats["lands"] += quantity
            
        is_synergy = False
        found_core = False
        
        for category, phrases in tag_definitions.items():
            matches = False
            for phrase in phrases:
                phrase = phrase.lower()
                if phrase in name or phrase in type_line or phrase in oracle_text:
                    matches = True
                    break
            
            if matches:
                if category in core_categories:
                    stats[category] += quantity
                    found_core = True
                else:
                    is_synergy = True
        
        if is_synergy and not found_core:
            stats["synergy"] += quantity

    warnings = []
    if stats["lands"] < 35:
        warnings.append("Low land count (less than 35)")
    if stats["ramp"] < 8:
        warnings.append("Low ramp count (less than 8)")
    if stats["card_draw"] < 8:
        warnings.append("Low card draw count (less than 8)")
    if stats["removal"] < 5:
        warnings.append("Low removal count (less than 5)")

    report = {
        "stats": stats,
        "warnings": warnings
    }

    if theme:
        theme_check = check_theme_packages(deck_cards, theme)
        report["theme_check"] = theme_check
        # Merge theme warnings
        report["warnings"].extend(theme_check["warnings"])

    return report
