import json
from typing import List, Dict, Any
from mtgcli.config import SEED_DATA_DIR
from mtgcli.cards.repository import CardRepository

def check_deck_quality(deck_cards: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyzes deck composition based on functional tags.
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
        "synergy": 0 # This one is harder, maybe anything with a tag not in the core categories?
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

    return {
        "stats": stats,
        "warnings": warnings
    }
