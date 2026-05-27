import json
from pathlib import Path
from typing import Optional
from mtgcli.cards.repository import CardRepository
from mtgcli.utils.json_io import read_json, write_json

def enrich_deck(deck_path: Path, db_path: Path, output_path: Optional[Path] = None) -> Path:
    """
    Enriches a simple deck JSON by looking up full card data from the SQLite database.
    
    Args:
        deck_path: Path to the input deck JSON.
        db_path: Path to the SQLite database.
        output_path: Path to save the enriched deck. If None, defaults to output/deck.enriched.json.
        
    Returns:
        The Path where the enriched deck was saved.
    """
    if output_path is None:
        output_path = Path("output/deck.enriched.json")
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    deck = read_json(deck_path)
    repo = CardRepository(str(db_path))
    
    enriched_deck = []
    
    for entry in deck:
        if isinstance(entry, str):
            # Handle simple string entries if they exist
            name = entry
            quantity = 1
            set_code = None
            collector_number = None
        else:
            name = entry.get('name')
            quantity = entry.get('quantity', 1)
            set_code = entry.get('set_code')
            collector_number = entry.get('collector_number')
            
        if not name:
            continue
            
        card_data = repo.get_card_by_exact_match(name, set_code, collector_number)
        
        if card_data:
            # Preserve quantity from the input
            card_data['quantity'] = quantity
            enriched_deck.append(card_data)
        else:
            print(f"Warning: Card '{name}' not found in database.")
            # Preserve the original entry if not found
            if isinstance(entry, dict):
                enriched_deck.append(entry)
            else:
                enriched_deck.append({"name": name, "quantity": quantity})
            
    write_json(output_path, enriched_deck)
    return output_path
