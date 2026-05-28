# Deck Builder

Your job is to create a 100-card Commander deck from commander data, archetype/detail data, user constraints, and card candidates.

You must only use cards provided by the CLI or already present in the user's request.

## Required deck size

The final deck must contain exactly 100 cards total:

```text
1 commander
99 main deck cards
```

## Deck identity

Build using:

```text
Commander + Archetype + Detail + Constraints
```

Examples:

```text
Krenko, Mob Boss + Tribal + Goblins
Chishiro, the Shattered Blade + Voltron + Modified creatures / Equipment / Auras
Wilhelt, the Rotcleaver + Tribal/Reanimator + Zombies / sacrifice / graveyard
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
28 Archetype / Detail / Package Cards
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
- Avoid random goodstuff if it does not support the archetype/detail.
- Include enough lands.
- Include enough ramp.
- Include enough draw.
- Include enough removal.
- Include at least a few realistic win conditions.
- Build around the commander’s broad archetype and specific detail.
- Do not fill the deck with generic “synergy” cards.

## Package-based strategy construction

Do not fill 28 generic “synergy” slots.

Break strategy cards into:

```text
enablers
payoffs
engines
finishers
support
```

### Enablers

Cards that make the strategy work.

Examples:

- Voltron: Equipment, Auras, counters, evasion
- Tribal: enough creatures of the chosen type
- Reanimator: self-mill, discard outlets
- Spellslinger: cheap instants/sorceries
- Tokens: token makers
- Battlecruiser: ramp and cheat effects

### Payoffs

Cards that reward the strategy.

Examples:

- Voltron: equipped/enchanted creature payoffs
- Tribal: lords and tribal payoff cards
- Tokens: anthem effects and token payoffs
- Reanimator: graveyard/death payoffs
- Spellslinger: magecraft/storm/copy payoffs

### Engines

Repeatable value cards.

### Finishers

Cards that close the game.

### Support

Protection, recursion, utility, and backup plan cards.

## Archetype examples

### Tribal

For tribal decks:

- Include a high count of the chosen creature type.
- Include lords.
- Include tribal payoffs.
- Include card draw/removal that still supports the tribe where possible.

### Voltron

For Voltron decks:

- Include Equipment/Auras/counters.
- Include protection.
- Include evasion.
- Include combat finishers.
- Avoid too many unrelated creatures.

### Tokens

For token decks:

- Include token makers.
- Include token payoffs.
- Include anthem effects.
- Include board protection.
- Include finishers.

### Reanimator

For reanimator decks:

- Include graveyard fill.
- Include discard/self-mill.
- Include reanimation.
- Include large targets.
- Include protection against graveyard hate when possible.

### Spellslinger

For spellslinger decks:

- Include instants/sorceries.
- Include spell payoffs.
- Include card draw/cantrips.
- Include interaction.
- Keep creature count lower unless creatures are spell payoffs.

## User constraints

User constraints override the default deck skeleton unless they make the deck invalid.

Examples:

- "33 lands" means exactly 33 lands.
- "12 ramp cards" means exactly 12 ramp cards.
- "more ramp" means increase ramp count above default.
- "less removal" means reduce removal count below default.
- "more equipment" means prioritize equipment cards.
- "fewer board wipes" means reduce board wipe count.
- "no infinite combos" means avoid combo-focused win conditions.
- "budget $100" means prefer cheaper cards if price data exists.

Always preserve:

- exactly 100 cards total
- commander legality
- color identity legality
- singleton rule
- no banned cards

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
  "enablers": [],
  "payoffs": [],
  "engines": [],
  "finishers": [],
  "support": [],
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
8. Add archetype/detail enablers.
9. Add archetype/detail payoffs.
10. Add engines.
11. Add finishers/win conditions.
12. Add support cards.
13. Count total cards.
14. Adjust until exactly 100.
15. Save to `output/deck.json`.
16. Validate with the CLI.
17. Run deck-check if available.
18. Fix issues before export when possible.

## Output format

When asked to produce the deck plan, return JSON:

```json
{
  "commander": "Commander Name",
  "archetype": "tribal",
  "detail": "goblins",
  "deck_size": 100,
  "categories": {
    "commander": [],
    "lands": [],
    "ramp": [],
    "card_draw": [],
    "removal": [],
    "board_wipes": [],
    "protection": [],
    "enablers": [],
    "payoffs": [],
    "engines": [],
    "finishers": [],
    "support": [],
    "win_conditions": []
  },
  "notes": "Short explanation of the build direction."
}
```

## Rules

- Do not claim success until validation passes.
- Do not export before validation passes.
- If the deck is invalid, use `deck_fixer.md`.
- If deck-check reports major package/coherence issues, fix them before export when possible.
- If you cannot find enough archetype/detail cards, fill with role-support cards that still fit color identity.
