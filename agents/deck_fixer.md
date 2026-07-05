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
6. Off-role package issues.
7. Missing package essentials.
8. Budget above allowed overage.
9. Coherence problems.
10. Nice-to-have improvements.

---

## Validation First

Run:

```bash
mtg validate --commander "<commander>" --deck output/deck.json --json-output
```

Partner:

```bash
mtg validate --commander "<commander A>" --partner "<commander B>" --deck output/deck.json --json-output
```

Common fixes:

| Error | Meaning | Fix |
|---|---|---|
| `card_not_found` | hallucinated/misspelled card | replace with real card |
| `not_commander_legal` | illegal in Commander | replace |
| `color_identity_violation` | outside color identity | replace |
| `invalid_deck_size` | wrong count | add/cut cards |
| `singleton_violation` | duplicate non-basic | remove duplicates |
| `commander_missing` | missing command-zone metadata | use `--commander` or structured JSON |

Do not force commander-zone cards into `main_deck` as a fix. Use structured metadata.

---

## Deck Size Fixes

Normal commander:

```text
1 commander + 99 main deck cards = 100
```

Partner:

```text
2 commanders + 98 main deck cards = 100
```

Use `deck-fill-lands` for missing basics. If deck is overfull, cut weakest off-plan cards first.

---

## Off-Role Results

If `suggest` returned off-role cards, do not use them.

Examples:

```text
normal lands under ramp
unrelated cards under card_draw
recursion counted as protection without actual protection
cheap cards with no synergy or role fit
```

Replace using role-correct searches:

```bash
mtg suggest --commander "<commander>" --role ramp --json-output
mtg suggest --commander "<commander>" --role card_draw --type creature --json-output
mtg search --oracle "draw a card" --type creature --json-output
```

---

## Budget Fixes

Budget is a maximum, not a target.

Only fix budget if:

```text
known total exceeds budget + allowed overage
strict budget mode rejects unknown prices
user requested stricter spending
```

Do not cut key synergy just because the deck is under budget.

A deck under budget is valid and does not need a "fix." If it is meaningfully
under budget (especially T1/T2), defer to the Budget Upgrade Review (BUILDER.md
Section 11) instead of forcing spending. Never auto-apply over-budget upgrades
without user approval, and respect the user's budget tolerance mode.

---

## Category Count Fixes

Use category-counts as guidance.

If compression made removal/wincons too low, use:

```text
recommended_range
need_score
uncompressed_target_count
practical deckbuilding judgment
```

Do not blindly obey compressed targets.

---

## Replacement Rules

Make every swap through the CLI, never by editing the list manually:

```bash
mtg deck-swap --deck output/deck.json --swap "<out>=<in>" --commander "<name>"   # validates before writing
mtg similar "<card being cut>"          # find functional replacements for a cut
mtg deck-gaps --deck ... --commander ...  # re-audit after fixes: category gaps AND plan_gaps (analyzer plan check) closed?
```

The fix loop ends at `mtg preflight` printing READY — never on memory of having checked.

When replacing a card:

1. Verify card exists.
2. Verify color identity.
3. Verify Commander legality.
4. Verify it performs the required role.
5. Prefer cards matching commander analysis tags if synergy matters.
6. Re-run validation.

---

## Final Rule

After any fix:

```bash
mtg validate --commander "<commander>" --deck output/deck.json --json-output
```

No final-build until validation passes.
