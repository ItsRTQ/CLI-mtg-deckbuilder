# Deck Builder

Purpose: build the deck using CLI data, user preferences, category-count guidance, commander analysis, and card ranking.

Do not invent cards. Do not create helper scripts.

---

## Build Sequence

1. Read `BUILDER.md`.
2. Collect user preferences with `agents/user-feedback.md` if needed.
3. Run commander lookup and `commander-analyze`.
4. Detect archetype/detail/constraints.
5. Run `category-counts` with commander analysis.
6. Plan package ranges from `recommended_range` and `need_score`.
7. Search/suggest candidates by role and package.
8. Rank candidates.
9. Build the nonland shell.
10. Write `output/decklist.txt`.
11. Convert using `deck-write --structured`.
12. Fill basics with `deck-fill-lands`.
13. Validate.
14. Fix errors.
15. Run deck-check.
16. Export and final-build only after validation passes.
17. Write `output/deck_explanation.md`.

---

## Command Setup

Analyze commander:

```bash
mtg commander-analyze --commander "<commander>" --output output/commander_analysis.json --json-output
```

Partner:

```bash
mtg commander-analyze --commander "<commander A>" --partner "<commander B>" --output output/commander_analysis.json --json-output
```

Plan categories:

```bash
mtg category-counts \
  --commander "<commander>" \
  --archetype "<archetype>" \
  --power-level <number> \
  --philosophy "<philosophy>" \
  --analysis output/commander_analysis.json \
  --json-output
```

---

## Package Planning

Use category-counts as soft guidance, not exact locks.

Plan from:

```text
recommended_range
uncompressed_target_count
need_score
slot_budget warnings
user constraints
commander_analysis role_pressures
```

If `compressed_target_count` pushes critical categories too low, use judgment and report it in Build Feedback.

Never let a forced low-fit archetype hide basic deck needs like ramp, draw, removal, or win conditions.

---

## Candidate Search

Use normal role suggestions for staples/structural pieces:

```bash
mtg suggest --commander "<commander>" --role ramp --limit 30 --json-output
mtg suggest --commander "<commander>" --role card_draw --limit 30 --json-output
mtg suggest --commander "<commander>" --role removal --limit 30 --json-output
mtg suggest --commander "<commander>" --role protection --limit 30 --json-output
```

Use synergy suggestions for commander-aligned packages:

```bash
mtg suggest --commander "<commander>" --role engine --synergy --analysis output/commander_analysis.json --limit 40 --json-output
mtg suggest --commander "<commander>" --role enabler --synergy --analysis output/commander_analysis.json --limit 40 --json-output
mtg suggest --commander "<commander>" --role payoff --synergy --analysis output/commander_analysis.json --limit 40 --json-output
mtg suggest --commander "<commander>" --role cheap --synergy --analysis output/commander_analysis.json --limit 30 --json-output
```

Never use `--role synergy`.

Add `--type <type>` to narrow a role to a specific card type (applied AFTER
role match — it never bypasses the role filter):

```bash
mtg suggest --commander "<commander>" --role card_draw --type creature --json-output
mtg suggest --commander "<commander>" --role ramp --type artifact --json-output
mtg suggest --commander "<commander>" --role payoff --type creature --synergy --json-output
```

`--type` is also on `search` / `search-tags` for effect-on-type lookups:

```bash
mtg search "draw a card" --type creature --json-output
mtg search "destroy target" --type instant --json-output
mtg search-tags card_draw --type creature --json-output
```

`--type` filters broad card type via `type_line`. It does not replace the
`type:<value>` query token; both can be combined. Supported: artifact,
creature, enchantment, instant, sorcery, planeswalker, land, battle (plurals
ok); aliases spell, permanent, nonland.

Suggestion and card-lookup JSON include creature `power` and `toughness`. Use them
when choosing creatures for combat, voltron, go-tall/go-wide, tribal, finisher, and
win-condition slots, and to gauge blocker quality. Treat missing or non-numeric P/T
(e.g. `*`) as unknown; do not invent values.

---

## Ramp and Draw Guardrails

Ramp suggestions must be real acceleration. Normal lands are not ramp.

Card draw suggestions must be actual draw/card advantage/filtering.

If suggest returns lands under ramp or unrelated cards under card_draw, manually filter and report the tool issue in Build Feedback.

---

## Deck File Creation

Write a plain list to:

```text
output/decklist.txt
```

Then create structured JSON:

```bash
mtg deck-write \
  --input output/decklist.txt \
  --output output/deck.json \
  --commander "<commander>" \
  --structured \
  --force
```

Partner:

```bash
mtg deck-write \
  --input output/decklist.txt \
  --output output/deck.json \
  --commander "<commander A>" \
  --partner "<commander B>" \
  --structured \
  --force
```

Commander-zone cards should not be inside `main_deck`.

---

## Land Filling

After the nonland shell:

```bash
mtg deck-fill-lands --deck output/deck.json --commander "<commander>" --output output/deck.json --force
```

Partner:

```bash
mtg deck-fill-lands --deck output/deck.json --commander "<commander A>" --partner "<commander B>" --output output/deck.json --force
```

Single commander target: 99 main deck cards.

Partner target: 98 main deck cards.

For landfall/landsmatter, prefer 38–42 lands unless the user asks for exact count.

---

## Validation

```bash
mtg validate --commander "<commander>" --deck output/deck.json --json-output
```

Do not finalize until valid.

If validation fails, use `agents/deck_fixer.md`.

---

## Optional Context

Explore:

```bash
mtg explore --commander "<commander>" --json-output
```

Combos:

```bash
mtg combos --commander "<commander>" --output output/commander_combos.json --json-output
```

Use these as signals, not mandatory includes.

---

## Build Feedback

Include only if useful. Examples:

```text
suggest returned off-role cards
validation/fill-lands conflict
category-counts compressed critical categories too far
explore JSON was invalid
combo data was missing or noisy
```
