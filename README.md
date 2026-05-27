# CLI-mtg-deckbuilder
This program intends to guide and help a CLI agent build a comprehensive MTG commander deck.

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
