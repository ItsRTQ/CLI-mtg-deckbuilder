# CLI-mtg-deckbuilder

Local CLI tools for building and validating Magic: The Gathering Commander decks.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows PowerShell:**
```powershell
.venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

### Initialize card data
```bash
python -m mtgcli.cli init-data
```

### Look up a card
```bash
python -m mtgcli.cli card "Sol Ring"
```

### Search cards
```bash
python -m mtgcli.cli search "draw a card" --colors RG
```

### Suggest cards by role
```bash
python -m mtgcli.cli suggest --commander "Chishiro, the Shattered Blade" --role ramp --limit 20
```

### Validate deck
```bash
python -m mtgcli.cli validate --commander "Chishiro, the Shattered Blade" --deck output/deck.json
```

### Export to Moxfield
```bash
python -m mtgcli.cli export output/deck.json --output output/deck.moxfield.txt
```

## Deck JSON Format

The CLI uses a specific JSON format for deck lists. This format is used by the `validate` and `export` commands.

### Example

```json
[
  {
    "quantity": 1,
    "name": "Chishiro, the Shattered Blade",
    "set_code": "nec",
    "collector_number": "77"
  },
  {
    "quantity": 1,
    "name": "Sol Ring",
    "set_code": "lcc",
    "collector_number": "299"
  },
  {
    "quantity": 18,
    "name": "Forest",
    "set_code": "m21",
    "collector_number": "274"
  }
]
```

### Rules

*   **Required Fields**: Every card object MUST have `quantity` (integer) and `name` (string).
*   **Recommended Fields**: `set_code` and `collector_number` are highly recommended. While the validator doesn't strictly require them, they are necessary for the `export` command to generate full Moxfield-compatible lines.
*   **Quantities**:
    *   **Basic Lands**: Can have a `quantity` greater than 1.
    *   **Non-basic Cards**: Should normally have a `quantity` of 1 to comply with Commander singleton rules.
