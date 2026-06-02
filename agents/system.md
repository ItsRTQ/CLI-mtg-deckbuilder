# System Agent

Purpose: keep the deckbuilding agent aligned with the project rules.

Read `BUILDER.md` first. It is the main guide.

---

## Core Contract

The `mtg` CLI is the source of truth for card data, legality, prices, validation, search, suggestions, export, and final-build saving.

The agent makes deckbuilding judgments, but it must not invent factual card data.

---

## Non-Negotiable Rules

1. Do not invent cards.
2. Do not use Commander-illegal cards.
3. Do not use cards outside commander color identity.
4. Do not finalize until `mtg validate` passes.
5. Do not save to `final-builds/` unless validation passes.
6. Do not create helper scripts such as `build_*.py` or `temp_*.py`.
7. Do not edit source code, seed files, README, `.env`, `.gitignore`, or agent files during normal deckbuilding.
8. Use `deck-write`, `deck-fill-lands`, `validate`, `deck-check`, `export`, and `final-build` instead of manual scripts.
9. `synergy` is not a role. Never use `--role synergy`. Use `--synergy` on a real role.
10. Commander-zone cards are metadata, not `main_deck` cards.

---

## Working Artifacts Allowed

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

Do not create other files unless the user explicitly requests it.

---

## Required Workflow Summary

1. Collect useful user preferences.
2. Run `mtg commander-analyze`.
3. Detect archetype/detail/constraints.
4. Run `mtg category-counts`.
5. Search/suggest/rank candidates.
6. Write `output/decklist.txt`.
7. Convert with `mtg deck-write --structured`.
8. Fill basics with `mtg deck-fill-lands`.
9. Validate.
10. Fix errors.
11. Run deck-check.
12. Export and final-build only after validation.
13. Explain the deck.
14. Include Build Feedback only if useful.

---

## Command-Zone Rule

Preferred deck JSON:

```json
{
  "commander": "Commander Name",
  "main_deck": []
}
```

Partner deck JSON:

```json
{
  "commanders": ["Commander A", "Commander B"],
  "main_deck": []
}
```

Single commander decks use 99 main deck cards. Partner decks use 98 main deck cards.

Do not add the commander into `main_deck` to satisfy validation.

---

## Suggest Rule

`role` = card function.

`--synergy` = card also supports the commander.

Examples:

```bash
mtg suggest --commander "Brago, King Eternal" --role ramp --json-output
mtg suggest --commander "Brago, King Eternal" --role ramp --synergy --analysis output/commander_analysis.json --json-output
```

`--role ramp --synergy` must still return real ramp.

---

## Tool Bug Handling

If a tool returns impossible data, finish as much as possible and report it in Build Feedback.

Examples:

```text
ramp suggestions returning lands
card_draw returning unrelated cards
explore JSON requiring strict=False
validate rejecting structured commander metadata
category-counts compressing critical categories to unrealistic numbers
```
