# Archetype and Detail Detector

Your job is to determine the deck identity from:

1. the user's request
2. the commander analysis
3. available CLI card data

This file replaces narrow “theme-only” thinking with:

```text
Commander + Archetype + Detail + Constraints
```

## Definitions

- **Commander**: the card leading the deck.
- **Archetype**: the broad deck strategy.
- **Detail**: the specific tribe, mechanic, flavor, or subtheme.
- **Constraints**: specific user requirements.

## Supported broad archetypes

Use these machine-friendly archetype names:

```text
battlecruiser
stax
spellslinger
control
pillowfort
voltron
group_hug
group_slug
reanimator
mill
theft
tribal
tokens
infect
```

## Input examples

User request:

```text
Create a Krenko, Mob Boss deck theme Goblins.
```

Identify:

```text
Commander: Krenko, Mob Boss
Archetype: tribal
Detail: goblins
Secondary archetype: tokens
```

User request:

```text
Create a Chishiro deck with 33 lands and more Equipment.
```

Identify:

```text
Commander: Chishiro, the Shattered Blade
Archetype: voltron or tokens
Detail: modified creatures, equipment, auras, +1/+1 counters
Constraint: exactly 33 lands
Preference: more equipment
```

## Tasks

Determine:

1. Commander name.
2. Primary broad archetype.
3. Secondary archetypes, if any.
4. Detail/subtheme.
5. Package plan.
6. Roles the deck needs.
7. User constraints.
8. Power direction.
9. What to avoid.

## Default assumptions

If the user does not specify a power level, build a focused casual deck.

Focused casual means:

- no need to optimize for cEDH
- avoid excessive infinite-combo focus unless the user asks for it
- include interaction
- keep the deck coherent
- prefer commander synergy over random staples

If the user does not specify budget, assume no strict budget, but avoid building only with expensive staples unless they strongly fit.

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

## Package model

Do not output only a generic “synergy” bucket.

Break strategy cards into packages:

```text
enablers
payoffs
engines
finishers
support
```

### Enablers

Cards that make the strategy work.

### Payoffs

Cards that reward the strategy.

### Engines

Repeatable value cards.

### Finishers

Cards that help close the game.

### Support

Protection, recursion, utility, and backup plan cards.

## Output format

Return only JSON.

```json
{
  "commander": "Krenko, Mob Boss",
  "archetype": "tribal",
  "detail": "goblins",
  "secondary_archetypes": ["tokens"],
  "power_level": "focused_casual",
  "budget": null,
  "package_plan": {
    "enablers": ["goblin creatures", "goblin token makers"],
    "payoffs": ["goblin lords", "goblin attack payoffs"],
    "engines": ["repeatable token makers", "sacrifice/value engines"],
    "finishers": ["haste enablers", "mass pump", "extra combat"],
    "support": ["protection", "removal", "card draw"]
  },
  "role_priorities": {
    "lands": "required",
    "ramp": "high",
    "card_draw": "high",
    "removal": "medium",
    "board_wipe": "low",
    "protection": "medium",
    "strategy_cards": "very_high",
    "win_conditions": "medium"
  },
  "constraints": {
    "exact_counts": {},
    "minimum_counts": {},
    "maximum_counts": {},
    "preferences": [],
    "avoid": []
  },
  "search_keywords": {
    "enablers": ["Goblin", "create Goblin token"],
    "payoffs": ["Goblins you control", "Goblin creatures you control", "whenever a Goblin"],
    "engines": ["create", "token", "sacrifice"],
    "finishers": ["haste", "additional combat", "creatures you control get"],
    "support": ["protect", "draw a card", "destroy target"]
  },
  "avoid_tags": ["off_color", "off_archetype", "unsupported_combo"],
  "notes": "Short explanation of why this archetype and detail fit."
}
```

## Rules

- If the user gives an archetype, respect it unless it conflicts with the commander.
- If the user gives a detail, preserve it.
- If the user gives no archetype, infer the archetype from the commander.
- If the user gives no detail, infer the detail from the commander text and type line.
- Do not choose an archetype only because it is popular.
- Choose the archetype because the commander supports it.
- Do not use cards outside commander color identity.
