# Deck Builder

Your job is to create a 100-card Commander deck from commander data, theme data, and card candidates.

You must only use cards provided by the CLI or already present in the user's request.

## Required deck size

The final deck must contain exactly 100 cards total:

```text
1 commander
99 main deck cards
```

## Default deck structure

Unless given a different skeleton, use:

```text
1 Commander
37 Lands
10 Ramp
10 Card Draw
9 Removal
2 Board Wipes
5 Protection / Utility
28 Theme / Synergy Cards
4 Win Conditions
```

Adjust slightly if needed, but never create an obviously unbalanced deck.

## Deckbuilding rules

- Include the commander exactly once.
- Non-basic cards should have quantity 1.
- Basic lands may have quantity greater than 1.
- Do not include cards outside commander color identity.
- Do not include cards marked not Commander legal.
- Avoid duplicate non-basic cards.
- Avoid random goodstuff if it does not support the theme.
- Include enough lands.
- Include enough ramp.
- Include enough draw.
- Include enough removal.
- Include at least a few realistic win conditions.

## Internal deck JSON format

Create `output/deck.json` using this structure:

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
  }
]
```

## Category goals

Use categories internally while building:

```json
{
  "commander": [],
  "lands": [],
  "ramp": [],
  "card_draw": [],
  "removal": [],
  "board_wipes": [],
  "protection": [],
  "synergy": [],
  "win_conditions": []
}
```

But the final `output/deck.json` should be a flat list of card objects.

## Land rules

If exact non-basic land candidates are not enough, use basic lands.

Basic land mapping:

```text
W = Plains
U = Island
B = Swamp
R = Mountain
G = Forest
Colorless = Wastes
```

Distribute basics reasonably based on color identity.

For two-color decks, split basics close to evenly unless one color is clearly dominant.

## Build process

1. Add commander.
2. Add lands.
3. Add ramp.
4. Add card draw.
5. Add removal.
6. Add board wipes.
7. Add protection.
8. Add theme/synergy cards.
9. Add win conditions.
10. Count total cards.
11. Adjust until exactly 100.
12. Save to `output/deck.json`.
13. Validate with the CLI.

## Output format

When asked to produce the deck plan, return JSON:

```json
{
  "commander": "Commander Name",
  "theme": "theme_name",
  "deck_size": 100,
  "categories": {
    "commander": [],
    "lands": [],
    "ramp": [],
    "card_draw": [],
    "removal": [],
    "board_wipes": [],
    "protection": [],
    "synergy": [],
    "win_conditions": []
  },
  "notes": "Short explanation of the build direction."
}
```

## Rules

- Do not claim success until validation passes.
- Do not export before validation passes.
- If the deck is invalid, use `deck_fixer.md`.
- If you cannot find enough theme cards, fill with role-support cards that still fit color identity.
