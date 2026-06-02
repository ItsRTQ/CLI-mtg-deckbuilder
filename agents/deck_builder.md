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

## Build Mode

Check the `build_mode` from user-feedback output before starting.

**Quick build:**

- Proceed directly after the 4-question flow.
- Do not ask additional questions unless the build is blocked.
- Apply sensible defaults for unasked preferences.

**Detailed build:**

- Apply all collected detailed preferences to category-counts arguments, archetype selection, philosophy, ramp count, interaction count, combo/tutor policy, theme strictness, and card ranking.
- You may ask small clarifying questions during the build at real decision points (see During-Build Clarification below).
- Maximum 2 during-build questions per build.

**How detailed preferences map to build decisions:**

```text
Playstyle: control/slow grind   → --philosophy control_grind
Playstyle: combo                → --philosophy combo_focus
Table: low salt                 → --philosophy low_salt
Ramp: high ramp                 → --philosophy explosive_fast
Interaction: heavy              → --philosophy interaction_heavy
Synergy max                     → --philosophy synergy_max
Combat pressure                 → --philosophy combat_pressure
```

---

## During-Build Clarification

In Detailed build mode only, you may ask a small question mid-build when the answer materially changes the deck.

Allowed cases:

```text
- Commander supports multiple equally strong archetypes
- category-count results conflict with stated user preference
- Budget is near overage and a key card is expensive
- Synergy search returns weak candidates
- Land count or ramp count requires a style decision
- Combo, tutor, or stax inclusion is unclear
```

Rules:

- Keep options multiple-choice.
- Always include Agent choice.
- If the user does not respond, choose the most coherent option and continue.
- Do not ask questions just to delay building.
- Maximum 2 during-build questions total per build.

---

## Required Deck Size

Single commander:

```text
1 commander
99 main deck cards
100 total
```

Partner commanders (two commanders with the Partner keyword):

```text
2 commanders
98 main deck cards
100 total
```

Both commanders appear exactly once.

Non-basic cards must be singleton.

Basic lands may have quantity greater than 1.

Color identity for partner decks is the combined color identity of both commanders.

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

## Combo Data (mtg combos)

When combos are relevant, fetch combo data first:

```bash
mtg combos \
  --commander "<commander>" \
  --output output/commander_combos.json \
  --json-output
```

Optionally filter by power bracket:

```bash
mtg combos \
  --commander "<commander>" \
  --max-bracket 3 \
  --limit 20 \
  --output output/commander_combos.json \
  --json-output
```

**Combo data is optional context — not mandatory includes.**

Use combo data for two purposes:

1. **If the user wants combos:** identify compact combo packages; check bracket/power appropriateness; verify all cards are legal, in color identity, and budget-appropriate; include only if power level and salt policy allow it.

2. **If the user does not want combos:** use individual combo pieces as synergy signal candidates; do not include full combo lines if the user asked for low-salt or no-combo.

Rules:

```text
- Do not force combos into every deck.
- Do not include combos in low-salt/friendly builds unless user wants them.
- Do not include high-bracket combos in low-power decks.
- All combo pieces must still pass: legality, color identity, budget, role balance, theme fit.
- Verify combo cards exist: mtg cards "Card A" "Card B" --json-output
```

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

## Category-Count Guidance

Before planning packages, run commander-analyze then category-counts:

```bash
# Step 1: generate the shared tactical map
mtg commander-analyze \
  --commander "<commander>" \
  --output output/commander_analysis.json \
  --json-output

# Step 2: use the analysis for richer commander scoring
mtg category-counts \
  --commander "<commander>" \
  --archetype <archetype> \
  --power-level <number> \
  --philosophy <philosophy> \
  --analysis output/commander_analysis.json \
  --json-output
```

For partner decks:

```bash
mtg commander-analyze \
  --commander "<commander>" \
  --partner "<partner>" \
  --output output/commander_analysis.json \
  --json-output

mtg category-counts \
  --commander "<commander>" \
  --partner "<partner>" \
  --archetype <archetype> \
  --power-level <number> \
  --philosophy <philosophy> \
  --json-output
```

If `output/commander_analysis.json` does not exist, category-counts still works — it falls back to live commander scoring.

Use the output as guidance:

- `need_score`: How important the system thinks this category is. Use this to judge priority even if `target_count` was compressed.
- `recommended_range`: Ideal range before slot-budget compression. Use this when planning packages.
- `target_count`: Post-compression final target. May be lower than the range if total demand exceeds nonland slots.

Category-count output is soft guidance — not a hard lock. Your deckbuilding judgment applies. If `compression_needed` is true, the system is flagging slot pressure; prioritize categories with the highest `need_score`.

If category-counts produces poor recommendations (slot pressure too extreme, wrong archetype fit, unrealistic numbers), note it in Build Feedback.

---

## Build Process

1. Add commander (or both commanders for partner decks).
2. Apply user feedback and constraints.
3. Run `mtg category-counts` to get package count targets.
4. Build role targets from power level, commander dependency, curve, engine, and category-counts guidance.
5. Select strategy packages first.
5. Select ramp package.
6. Select draw/card advantage/search.
7. Select removal/interaction.
8. Select protection/resilience.
9. Select win conditions.
10. Build preliminary nonland main deck (67 cards for single commander, 66 for partner).
11. Calculate lands.
12. Add nonbasic lands and mana fixing.
13. Cut or add nonlands to reach target size (99 for single, 98 for partner).
14. Write `output/decklist.txt` in plain text format (one card per line, `1 Card Name`).
15. Convert using structured output (removes commander from main_deck automatically):
    `mtg deck-write --input output/decklist.txt --output output/deck.json --commander "<commander>" --structured --force`
    For partner decks: add `--partner "<partner>"`.
16. Fill remaining basics: `mtg deck-fill-lands --deck output/deck.json --commander "<commander>" --output output/deck.json --force`
    - deck-fill-lands automatically removes the commander from the main deck count if it appears in a flat list.
    - Do NOT count the commander as part of the 99 (or 98 for partner) main deck cards.
17. Validate with CLI.
18. Fix with `deck_fixer.md` if invalid.
19. Run deck-check if available.
20. Fix major coherence issues.
21. Export only after validation passes.

Do not create helper Python scripts to generate `output/deck.json`. Use `deck-write` and `deck-fill-lands` instead.

### Ramp package rule

Ramp cards must accelerate mana. Normal lands are **not** ramp.

If `mtg suggest --role ramp` returns basic lands or tapped utility lands, discard those results — do not include them in the ramp package.

Valid ramp: mana rocks, mana dorks, rituals, Treasure makers, land search (Cultivate/Kodama's Reach), extra land drops, meaningful cost reducers.

Not ramp: Plains, Island, Command Tower, Arcane Sanctum, Evolving Wilds, or any land that only taps for mana.

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
  { "quantity": 1, "name": "Card Name" }
]
```

Do not include `set_code`, `collector_number`, rarity, or printing-specific fields in the deck list.

---

## Rules

- Do not claim success until validation passes.
- Do not export before validation passes.
- Do not use unverified cards.
- Do not create commander-specific templates.
- Use the commander's engine and user preferences to decide package balance.
- Preserve user constraints.

---

## Tool-contract notes

### Command zone (validate / deck-fill-lands / deck-write)

- Keep commander-zone cards OUT of `main_deck`. Use structured deck JSON:
  `{ "commander": "...", "main_deck": [...] }`.
- Run: `deck-write --commander "<C>" --structured` → `deck-fill-lands --commander "<C>"`
  → `validate --commander "<C>"`. They agree on command-zone handling; structured
  shape is preserved through fill-lands and validates without manual fixups.
- Main deck = 99 (single) / 98 (partner); total incl. commander(s) = 100.
- `commander_missing` no longer fires just because the commander isn't in `main_deck`.

### suggest

- Ramp must be real acceleration, never normal mana-tapping lands.
- card_draw must be actual draw/card advantage/filtering.
- Strict roles never return empty `matched_tags`; `--synergy` only narrows after
  role match. Off-role results are a tool bug — do not include them.

### category-counts

- Plan from `recommended_range` / `uncompressed_target_count`. Compressed targets
  are slot-pressure outputs, not hard locks. Heed `practical_floor_warnings` and
  `fit_confidence` / `forced_archetype_warning` on forced low-fit archetypes.
