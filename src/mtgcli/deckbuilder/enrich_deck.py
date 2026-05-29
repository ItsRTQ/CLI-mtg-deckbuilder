from pathlib import Path
from typing import Optional
from mtgcli.cards.repository import CardRepository
from mtgcli.utils.json_io import read_json, write_json

def enrich_deck(deck_path: Path, db_path: Path, output_path: Optional[Path] = None) -> Path:
    """
    Enriches a simple deck JSON by looking up full card data from the SQLite database.
    Deck entries only need 'name' and 'quantity'.
    """
    if output_path is None:
        output_path = Path("output/deck.enriched.json")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    deck = read_json(deck_path)
    repo = CardRepository(str(db_path))

    enriched_deck = []

    for entry in deck:
        if isinstance(entry, str):
            name = entry
            quantity = 1
        else:
            name = entry.get('name')
            quantity = entry.get('quantity', 1)

        if not name:
            continue

        card_data = repo.get_card_by_exact_name(name)

        if card_data:
            card_data['quantity'] = quantity
            enriched_deck.append(card_data)
        else:
            print(f"Warning: Card '{name}' not found in database.")
            if isinstance(entry, dict):
                enriched_deck.append(entry)
            else:
                enriched_deck.append({"name": name, "quantity": quantity})

    write_json(output_path, enriched_deck)
    return output_path
