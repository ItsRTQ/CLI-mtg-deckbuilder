# Agent Usage Guide

This project is a local MTG Commander deckbuilding tool.

The agent should use the markdown files in `agents/` as behavior instructions and use the Python CLI commands as the source of truth.

## Deck identity model

When the user asks for a deck, separate the request into:

```text
Commander + Archetype + Detail + Constraints
```

Examples:

```text
Commander: Krenko, Mob Boss
Archetype: Tribal
Detail: Goblins
Constraints: 33 lands
```

```text
Commander: Chishiro, the Shattered Blade
Archetype: Voltron
Detail: Modified creatures, Equipment, Auras, +1/+1 counters
```

```text
Commander: Wilhelt, the Rotcleaver
Archetype: Reanimator or Tribal
Detail: Zombies, sacrifice, graveyard value
```

## Main workflow

When the user asks:

```text
Build a deck with <commander> as commander.
```

Do this:

1. Read `agents/system.md`.
2. Read `agents/commander_analyzer.md`.
3. Look up the commander:

```bash
mtg card "<commander>" --json-output
```

4. Analyze the commander using the returned JSON.
5. Read `agents/theme_detector.md`.
6. Determine commander, archetype, detail, and constraints.
7. Search/suggest candidate cards by role:

```bash
mtg suggest --commander "<commander>" --role ramp --json-output
mtg suggest --commander "<commander>" --role card_draw --json-output
mtg suggest --commander "<commander>" --role removal --json-output
mtg suggest --commander "<commander>" --role board_wipe --json-output
mtg suggest --commander "<commander>" --role protection --json-output
```

8. For strategy cards, prefer package-based suggestions if the CLI supports them:

```bash
mtg suggest --commander "<commander>" --role synergy --archetype "<archetype>" --package enablers --detail "<detail>" --json-output
mtg suggest --commander "<commander>" --role synergy --archetype "<archetype>" --package payoffs --detail "<detail>" --json-output
mtg suggest --commander "<commander>" --role synergy --archetype "<archetype>" --package engines --detail "<detail>" --json-output
mtg suggest --commander "<commander>" --role synergy --archetype "<archetype>" --package finishers --detail "<detail>" --json-output
```

If the CLI uses `--theme` instead of `--archetype`, use the supported option.

9. Read `agents/card_ranker.md`.
10. Rank candidate cards by function:

```text
enabler
payoff
engine
finisher
support
ramp
draw
removal
protection
```

11. Read `agents/deck_builder.md`.
12. Create `output/deck.json`.
13. Validate:

```bash
mtg validate --commander "<commander>" --deck output/deck.json --json-output
```

14. If validation fails:
    - read `agents/deck_fixer.md`
    - fix `output/deck.json`
    - validate again

15. Run deck-check if available:

```bash
mtg deck-check --commander "<commander>" --deck output/deck.json --archetype "<archetype>" --json-output
```

If the CLI uses `--theme`, use the supported option.

16. If deck-check reports major issues:
    - fix package balance
    - validate again

17. Export:

```bash
mtg export output/deck.json --output output/deck.moxfield.txt
```

18. Read `agents/deck_explainer.md`.
19. Create final explanation:

```text
output/deck_explanation.md
```

## User constraints

If the user gives specific constraints, apply them before using the default deck skeleton.

Examples:

- "33 lands" means use exactly 33 lands.
- "12 ramp cards" means use exactly 12 ramp cards.
- "more ramp" means increase ramp count above the default.
- "less removal" means reduce removal count below the default.
- "more creatures" means prioritize creature cards.
- "more Goblins" means prioritize Goblin cards.
- "more equipment" means increase Equipment cards.
- "fewer board wipes" means reduce board wipe count.
- "avoid infinite combos" means avoid combo-focused win conditions.
- "budget $100" means prefer cheaper cards if price data exists.
- "casual" means avoid overly optimized fast mana/tutor-heavy choices.
- "high power" means allow stronger staples and more efficient cards.

User constraints override the default skeleton unless they would make the deck invalid.

Always preserve:

- exactly 100 cards total
- commander legality
- color identity legality
- singleton rule
- no banned cards

## Required rule

Never give the user a final deck until validation passes.
