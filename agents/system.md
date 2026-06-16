# System Agent

Purpose: keep the deckbuilding agent aligned with project rules.

Read `BUILDER.md` first. It is the source of workflow truth.

---

## Core Contract

The `mtg` CLI is the source of truth for:

```text
card data
power/toughness
oracle text
legality
color identity
prices
search/suggest results
validation
exports/final builds
```

The agent makes deckbuilding decisions, but it must not invent factual card data.

---

## Non-Negotiable Rules

1. Do not invent cards.
2. Do not use Commander-illegal cards.
3. Do not use cards outside commander color identity.
4. Do not finalize until `mtg validate` passes.
5. Do not save to `final-builds/` unless validation passes.
6. Do not create helper scripts such as `build_*.py` or `temp_*.py`.
7. Do not edit source code, seed files, README, `.env`, `.gitignore`, or agent docs during normal deckbuilding.
8. Use `deck-write`, `deck-fill-lands`, `validate`, `deck-check`, `export`, and `final-build` instead of manual scripts.
9. `synergy` is not a role. Use `--synergy` on a real role.
10. Commander-zone cards are metadata, not `main_deck` cards.

---

## Allowed Artifacts

```text
output/decklist.txt
output/deck.json
output/deck.enriched.json
output/deck.moxfield.txt
output/deck_explanation.md
output/validation_report.json
output/commander_analysis.json
output/commander_combos.json
final-builds/<build-name>/
```

---

## Build Mindset

Use the tools in this order:

```text
understand commander
collect preferences
plan packages
search/suggest candidates
rank cards
build shell
write deck JSON
fill lands
validate
fix
explain
final-build
```

Do not skip validation. Do not treat suggestions as automatic includes.

---

## Error Handling

If a tool returns bad candidates, do not blindly use them. Report it in Build Feedback.

Examples:

```text
ramp search returning normal lands
card_draw returning unrelated cards
category-counts compressing interaction too aggressively
unknown price cards affecting budget confidence
validation/fill-land mismatch
```
