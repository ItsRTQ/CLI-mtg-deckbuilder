from typing import List, Dict, Any

COLOR_TO_LAND = {
    "W": "Plains",
    "U": "Island",
    "B": "Swamp",
    "R": "Mountain",
    "G": "Forest"
}

def suggest_basic_lands(color_identity: List[str], total_count: int = 37) -> List[Dict[str, Any]]:
    """
    Suggests a basic land base based on color identity.
    Simple distribution for now.
    """
    if not color_identity:
        return [{"name": "Wastes", "quantity": total_count}]
    
    lands = []
    colors = [c for c in color_identity if c in COLOR_TO_LAND]
    
    if not colors:
        return [{"name": "Wastes", "quantity": total_count}]
        
    base_count = total_count // len(colors)
    remainder = total_count % len(colors)
    
    for i, color in enumerate(colors):
        quantity = base_count + (1 if i < remainder else 0)
        lands.append({
            "name": COLOR_TO_LAND[color],
            "quantity": quantity
        })
        
    return lands
