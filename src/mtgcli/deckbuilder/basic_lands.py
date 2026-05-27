from typing import List, Dict, Any


def suggest_basic_lands(color_identity: List[str], count: int) -> List[Dict[str, Any]]:
    """
    Suggests a distribution of basic lands based on color identity and total count.
    Distributes lands as evenly as possible.
    """
    mapping = {
        "W": "Plains",
        "U": "Island",
        "B": "Swamp",
        "R": "Mountain",
        "G": "Forest"
    }
    
    # Handle colorless identity
    if not color_identity:
        return [{
            "quantity": count,
            "name": "Wastes",
            "set_code": "",
            "collector_number": "",
            "is_basic_land": True
        }]
    
    # Sort for deterministic output
    colors = sorted([c.upper() for c in color_identity if c.upper() in mapping])
    
    if not colors:
        # If no valid WUBRG colors found but identity wasn't empty
        # (shouldn't happen with valid Scryfall data)
        return [{
            "quantity": count,
            "name": "Wastes",
            "set_code": "",
            "collector_number": "",
            "is_basic_land": True
        }]

    num_colors = len(colors)
    base_count = count // num_colors
    remainder = count % num_colors
    
    results = []
    for i, color in enumerate(colors):
        land_name = mapping[color]
        amount = base_count + (1 if i < remainder else 0)
        
        if amount > 0:
            results.append({
                "quantity": amount,
                "name": land_name,
                "set_code": "",
                "collector_number": "",
                "is_basic_land": True
            })
            
    return results
