# Deck Builder

Purpose: build the deck using CLI data, user preferences, category-count guidance, commander analysis, and card ranking.

Do not invent cards. Do not create helper scripts.

---

## Build Sequence

1. Read `BUILDER.md`.
2. Collect user preferences if needed.
3. Run `commander-analyze`.
4. Detect archetype, detail, constraints, and build mode.
5. Run `category-counts` with commander analysis.
6. Optionally run `explore` / `combos` for context.
7. Search/suggest candidates by role and package.
8. Rank candidates.
9. Build the nonland shell.
10. Write `output/decklist.txt`.
11. Convert using `deck-write --structured`.
12. Fill basics with `deck-fill-lands`.
13. Validate.
14. Fix errors.
15. Run deck-check and budget checks.
16. If under budget threshold, run Budget Upgrade Review: show under-budget upgrades and optional over-budget high-impact options, then ask the user what to apply (see BUILDER.md Section 11).
17. Apply selected upgrades, then re-run validate, deck-check, and budget-check.
18. Write `output/deck_explanation.md`.
19. Final-build only after the Budget Upgrade Review decision is resolved and validation passes.

---

## Core Commands

Commander analysis:

```bash
mtg commander-analyze --commander "<commander>" --output output/commander_analysis.json --json-output
```

Category planning:

```bash
mtg category-counts \
  --commander "<commander>" \
  --archetype "<archetype>" \
  --power-level <number> \
  --philosophy "<philosophy>" \
  --analysis output/commander_analysis.json \
  --json-output
```

Write structured deck:

```bash
mtg deck-write \
  --input output/decklist.txt \
  --output output/deck.json \
  --commander "<commander>" \
  --structured \
  --force
```

Fill lands:

```bash
mtg deck-fill-lands --deck output/deck.json --commander "<commander>" --output output/deck.json --force
```

Validate:

```bash
mtg validate --commander "<commander>" --deck output/deck.json --json-output
```

Partner decks should include `--partner` on each relevant command.

---

## Commander and Main Deck

Do not put commander-zone cards in `main_deck`.

Use structured deck output:

```json
{
  "commander": "<Commander>",
  "main_deck": []
}
```

Partner:

```json
{
  "commanders": ["<Commander A>", "<Commander B>"],
  "main_deck": []
}
```

---

## Package Planning

Use category-counts for ranges, not hard locks.

Prioritize:

```text
commander engine
required roles
user preferences
category-count recommended_range
validation legality
budget/salt/power limits
```

If compressed targets look misleading, use `recommended_range`, `need_score`, and deckbuilding judgment.

---

## Search and Suggest

Use role suggestions:

```bash
mtg suggest --commander "<commander>" --role ramp --json-output
mtg suggest --commander "<commander>" --role engine --synergy --analysis output/commander_analysis.json --json-output
mtg suggest --commander "<commander>" --role card_draw --type creature --json-output
```

Use search for precise effects:

```bash
mtg search --oracle "can't be blocked" --oracle target --oracle creature --json-output
mtg search --oracle "draw a card" --type creature --json-output
mtg search "type:vampire" --type creature --json-output
```

Rules:

```text
Never use --role synergy.
--synergy modifies a real role.
--type narrows the card type and never bypasses role matching.
Repeated --oracle / --name / --card-type filters are AND filters.
```

---

## Decklist Writing

Write `output/decklist.txt` as a simple list of main-deck cards.

Avoid including the commander in the main deck list when using structured output.

Then run `deck-write --structured`.

Do not create Python scripts to generate JSON.

---

## Lands

Build the nonland shell first. Then use `deck-fill-lands`.

Normal decks:

```text
99 main deck cards after fill
```

Partner decks:

```text
98 main deck cards after fill
```

Landfall/landsmatter usually targets 38–42 lands. Do not hard-lock exact 40 unless user asked.

---

## Combos and Explore

Use combos/explore as optional context:

```bash
mtg explore --commander "<commander>" --json-output
mtg combos --commander "<commander>" --output output/commander_combos.json --json-output
```

Do not include full combos unless user preference, power level, and salt policy allow them.

---

## Final Build

Only after validation passes:

```bash
mtg final-build \
  --deck output/deck.json \
  --commander "<commander>" \
  --theme "<theme>" \
  --bracket T3 \
  --explanation output/deck_explanation.md
```
