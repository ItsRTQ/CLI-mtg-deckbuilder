# Deck Fixer

Purpose: repair a deck after validation, deck-check, budget, or coherence issues.

Fix using CLI data. Do not invent cards. Do not create helper scripts.

---

## Fix Priority

1. Validation errors.
2. Illegal cards or color identity violations.
3. Wrong deck size.
4. Singleton violations.
5. Missing commander metadata.
6. Missing package essentials.
7. Budget above allowed limit.
8. Coherence problems.
9. Nice-to-have improvements.

---

## Validation Fixes

Run:

```bash
mtg validate --commander "<commander>" --deck output/deck.json --json-output
```

Partner:

```bash
mtg validate --commander "<commander A>" --partner "<commander B>" --deck output/deck.json --json-output
```

Fix common errors:

| Error | Meaning | Fix |
|---|---|---|
| `card_not_found` | hallucinated/misspelled card | replace with real card |
| `not_commander_legal` | illegal in Commander | swap card |
| `color_identity_violation` | outside color identity | swap card |
| `invalid_deck_size` | wrong count | add/cut cards |
| `singleton_violation` | duplicate non-basic | remove duplicates |
| `commander_missing` | missing commander metadata | provide `--commander` or structured metadata |

Do not put commander inside `main_deck` just to appease validation. Structured metadata is preferred.

---

## Command-Zone Fixes

Preferred deck JSON:

```json
{
  "commander": "Commander Name",
  "main_deck": []
}
```

If a flat list contains the commander, validation should treat it as command-zone metadata. If not, fix with structured `deck-write`.

Use:

```bash
mtg deck-write --input output/decklist.txt --output output/deck.json --commander "<commander>" --structured --force
mtg deck-fill-lands --deck output/deck.json --commander "<commander>" --output output/deck.json --force
mtg validate --commander "<commander>" --deck output/deck.json --json-output
```

---

## Deck Size Fixes

Single commander:

```text
99 main deck + 1 commander = 100
```

Partner:

```text
98 main deck + 2 commanders = 100
```

Use `deck-fill-lands` for missing basics. Do not manually script land math.

---

## Suggest Fixes

If replacing cards, use valid role suggestions.

```bash
mtg suggest --commander "<commander>" --role removal --limit 20 --json-output
mtg suggest --commander "<commander>" --role protection --limit 20 --json-output
mtg suggest --commander "<commander>" --role engine --synergy --analysis output/commander_analysis.json --limit 20 --json-output
```

Never use `--role synergy`.

Reject off-role results manually if they appear.

---

## Budget Fixes

Budget is a maximum, not a target.

Only reduce cost when above the allowed limit or user asks.

Default overage allowance: 10%.

Unknown-price cards are allowed by default but must be reported.

When cutting for budget:

1. Cut expensive low-synergy cards first.
2. Preserve core engine pieces.
3. Preserve required role balance.
4. Do not make the deck incoherent just to save money.

---

## Category-Counts Fixes

Use category-counts to identify missing or overfilled categories, but do not obey compressed targets blindly.

Prefer:

```text
recommended_range
uncompressed_target_count
need_score
```

If compression pushes removal or win conditions too low, use judgment and report it.

---

## Final Check

After fixes:

```bash
mtg validate --commander "<commander>" --deck output/deck.json --json-output
mtg deck-check --commander "<commander>" --deck output/deck.json --json-output
```

Only then export/final-build.
