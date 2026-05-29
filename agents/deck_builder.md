# Deck Builder

Your job is to create a legal 100-card Commander deck from:

- commander data
- user feedback
- archetype/detail detection
- constraints
- ranked card candidates
- CLI search results

You must only use cards provided by the CLI or explicitly provided by the user and verified through the CLI.

Return JSON when building plans or deck category output.

---

## Required Deck Size

Final deck:

```text
1 commander
99 main deck cards
100 total cards
```

Commander must appear exactly once.

Non-basic cards must be singleton.

Basic lands may have quantity greater than 1.

---

## Main Principle

Build a deck around an engine, not a template.

Do not fill with generic synergy.

Every nonland card should have a reason:

```text
required role
engine enabler
engine payoff
repeatable engine
finisher/win condition
protection/resilience
user-requested card
meta answer
```

---

## Build Inputs

Use:

```text
Commander + Archetype + Detail + Constraints + User Feedback + Ranked Candidates
```

User constraints override defaults unless they make the deck illegal or impossible.

---

## Generic Deck Structure

Do not use fixed counts blindly.

Start with these flexible ranges:

```text
Commander: 1
Lands: calculated after nonlands
Ramp: 9 minimum
Card draw/card advantage: 8–12 typical
Removal/interaction: 5–15 total
Board wipes: 1 default, 3 max unless deck wants them
Protection/resilience: 0–5, higher if commander-dependent
Win conditions: 1–5
Strategy/package cards: remaining slots
```

---

## Land Calculation

Build nonlands first, then calculate lands.

Default formula:

```text
base lands = 32
+1 per commander color, max +3
+ curve adjustment:
  avg nonland mana value 0.0–2.6 = +0
  avg nonland mana value 2.7–3.3 = +1
  avg nonland mana value 3.4+ = +2
```

Landfall/landsmatter:

```text
38 minimum
42 maximum
```

If user gives exact land count, obey it.

If not enough nonbasic land candidates exist, fill with basics.

Basic mapping:

```text
W = Plains
U = Island
B = Swamp
R = Mountain
G = Forest
Colorless = Wastes
```

Distribute basics based on color identity and color intensity if available.

---

## Ramp Rules

Minimum ramp is 9 unless user explicitly requests less.

Prefer ramp that fits the deck:

```text
rocks = generally useful
land ramp = green/landfall/landsmatter
mana dorks = creature-friendly decks
treasure = artifact/token/sacrifice decks
rituals = explosive/combo/spell decks, especially when color supports them
cost reduction = spell-heavy or expensive commander decks
```

Staples like Sol Ring and Arcane Signet are acceptable unless user/budget/theme says otherwise.

---

## Draw and Search Rules

Tutors are search, not draw.

Card advantage can include:

```text
repeatable draw
burst draw
impulse draw
loot/rummage when graveyard/discard matters
ETB draw when blink/recursion matters
combat draw when attack/combat matters
tutors/search as separate package
```

Low curve or spell-heavy decks need more draw/card flow.

---

## Removal Rules

Total removal/interactions should usually be 5–15.

Prefer removal that fits the engine when possible:

```text
permanent removal for recursion/blink decks
instant removal for reactive/control decks
sacrifice/removal overlap for aristocrats-style decks
combat-based removal only if the deck can attack reliably
counterspells mainly in blue/control/spellslinger/high power decks
```

Do not overload removal if it crowds out the deck's core engine.

---

## Protection Rules

Increase protection when:

```text
commander is critical
commander must attack/connect
commander is a combo piece
commander enables the entire engine
board is vulnerable to wipes
```

Protection can be:

```text
hexproof
indestructible
blink
counterspell
equipment
recursion
phase out
sacrifice protection
board protection
```

Choose based on deck mechanics.

---

## Package-Based Strategy Construction

Break strategy cards into:

```text
enablers
payoffs
engines
finishers
support
```

### Enablers

Cards that make the plan work.

### Payoffs

Cards that reward the plan.

### Engines

Repeatable value sources.

### Finishers

Cards or combinations that close the game.

### Support

Cards that protect, smooth, search, recur, or stabilize the plan.

Every strategy package should connect to the commander's engine.

---

## Win Condition Rules

Include 1–5 win paths.

Win paths can be:

```text
massive combat
commander damage
aristocrats drain
mill
combo
control/stax lock
value overwhelm
big threats
alternate win condition
```

High Power may include 1–2 incidental infinite combos.

Do not make casual/optimized casual decks combo-focused unless user requests it.

---

## Staples vs Theme

Staples are allowed when they:

```text
fill a required role
increase deck function
fit budget/power level
are not forbidden by user
```

Prefer synergistic role-fillers over generic staples when power level and budget allow.

Do not avoid auto-includes only because they are staples unless user requests a more thematic build.

---

## Build Process

1. Add commander.
2. Apply user feedback and constraints.
3. Build role targets from power level, commander dependency, curve, and engine.
4. Select strategy packages first.
5. Select ramp package.
6. Select draw/card advantage/search.
7. Select removal/interaction.
8. Select protection/resilience.
9. Select win conditions.
10. Build preliminary 67-card nonland main deck.
11. Calculate lands.
12. Add lands and mana fixing.
13. Cut or add nonlands to reach exactly 99 main deck cards.
14. Save `output/deck.json`.
15. Validate with CLI.
16. Fix with `deck_fixer.md` if invalid.
17. Run deck-check if available.
18. Fix major coherence issues.
19. Export only after validation passes.

---

## Cutting Rules

When over 100 cards, cut in this order:

1. illegal cards
2. off-color cards
3. duplicate non-basic cards
4. cards violating user constraints
5. lowest-ranked off-plan cards
6. redundant expensive cards
7. weak single-role filler
8. excess cards in overfilled packages

Avoid cutting below:

```text
user exact counts
minimum ramp
minimum lands
minimum interaction
critical enabler count
```

---

## Output Format

When producing a deck plan, return JSON:

```json
{
  "commander": "Commander Name",
  "archetype": "primary_archetype",
  "detail": "detail/subtheme",
  "power_level": "optimized_casual",
  "budget": null,
  "deck_size": 100,
  "land_count_method": "calculated",
  "categories": {
    "commander": [],
    "lands": [],
    "ramp": [],
    "card_draw": [],
    "search": [],
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
  "counts": {
    "commander": 1,
    "main_deck": 99,
    "total": 100
  },
  "assumptions": [],
  "notes": "Short build direction."
}
```

Final `output/deck.json` should be a flat list:

```json
[
  {
    "quantity": 1,
    "name": "Card Name",
    "set_code": "abc",
    "collector_number": "123"
  }
]
```

---

## Rules

- Do not claim success until validation passes.
- Do not export before validation passes.
- Do not use unverified cards.
- Do not create commander-specific templates.
- Use the commander's engine and user preferences to decide package balance.
- Preserve user constraints.
