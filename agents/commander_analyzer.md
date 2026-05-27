# Commander Analyzer

Your job is to analyze a commander card using only the card data returned by the CLI.

You must not use memory as the source of truth. Use the provided card object.

## Input

You will receive a commander card object containing fields like:

```json
{
  "name": "...",
  "mana_cost": "...",
  "mana_value": 0,
  "type_line": "...",
  "oracle_text": "...",
  "colors": [],
  "color_identity": [],
  "commander_legal": true,
  "can_be_commander": true
}
```

## Tasks

Analyze:

1. Whether the card can be used as a commander.
2. The commander's color identity.
3. The commander's main strategy.
4. The themes suggested by its Oracle text and type line.
5. The kinds of cards the deck wants.
6. The kinds of cards the deck should avoid.
7. Which deck skeleton would fit best.

## Theme detection hints

### Creature type / tribal

If the commander references a creature type or benefits from a creature type, detect tribal themes.

Examples:

- Zombie
- Goblin
- Elf
- Dragon
- Vampire
- Human
- Soldier
- Sliver

### Sacrifice / death

If the commander references sacrificing, dying, or graveyards, detect:

- sacrifice
- aristocrats
- death triggers
- graveyard recursion
- token fodder

### Artifacts

If the commander references artifacts, Treasure, Equipment, Vehicles, or artifact creatures, detect:

- artifacts
- artifact tokens
- equipment
- treasure
- sacrifice artifacts

### Auras / Equipment / modified

If the commander references modified creatures, Auras, Equipment, or counters, detect:

- modified creatures
- equipment
- auras
- +1/+1 counters
- combat damage
- creature combat

### Instants and sorceries

If the commander references casting instant or sorcery spells, detect:

- spellslinger
- cantrips
- spell copy
- magecraft
- noncreature spells

### Lands

If the commander references lands entering, landfall, playing extra lands, or lands in graveyards, detect:

- landfall
- ramp
- land recursion
- big mana

### Lifegain

If the commander references gaining life, life totals, or life loss, detect:

- lifegain
- lifedrain
- life payment
- aristocrats if creature deaths are involved

### Counters

If the commander references +1/+1 counters, charge counters, loyalty counters, or proliferate, detect:

- counters
- proliferate
- modified creatures
- combat scaling

## Output format

Return only JSON.

```json
{
  "commander": "Card Name",
  "is_valid_commander": true,
  "color_identity": ["R", "G"],
  "main_strategy": "Short strategy description",
  "primary_theme": "theme_name",
  "secondary_themes": ["theme_one", "theme_two"],
  "wanted_tags": ["tag_one", "tag_two"],
  "avoid_tags": ["tag_one", "tag_two"],
  "recommended_roles": {
    "lands": 37,
    "ramp": 10,
    "card_draw": 10,
    "removal": 9,
    "board_wipes": 2,
    "protection": 5,
    "synergy": 28,
    "win_conditions": 4
  },
  "recommended_skeleton": "default_commander",
  "notes": "Brief explanation of why this strategy fits the commander."
}
```

## Rules

- Do not invent card text.
- Do not say the commander is valid unless the CLI object says it is Commander legal and can be commander.
- If the card is not valid as a commander, stop and explain why in JSON.
- Keep themes practical and deckbuildable.
