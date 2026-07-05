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
4. Do not finalize until `mtg preflight` prints `READY` (it runs validate + size + legality + singleton + color identity + budget in one gate; exit code 0). Never declare a deck done on memory of having checked — run the gate.
5. Do not save to `final-builds/` unless validation passes.
6. Do not create helper scripts (`build_*.py`, `temp_*.py`) that generate or decide deck content. Read-only inspection of CLI output (piping `--json-output` to `jq` / `json.tool` to filter or pretty-print) is allowed.
7. Do not edit source code, seed files, README, `.env`, `.gitignore`, or agent docs during normal deckbuilding.
8. Use official CLI commands instead of manual scripts: `deck-write`, `deck-fill-lands`, `validate`, `deck-check`, `export`, `final-build`, and `preflight`. To edit the list, use `deck-swap` (validates before writing) — never a `sed`/`python` replace. To read without scripting, use `cards-batch --verify`, `card --field`, `category-counts --table`, and `budget --by-card`. For analysis, use `analyze-card` (evidence-based card read), `deck-gaps` (audit vs commander plan), `similar` / `complements` (functional neighbors). Every command supports `--json-output`, and `--log` (any command) appends to the audit trail consolidated by `mtg report`.
9. `synergy` is not a role. Use `--synergy` on a real role.
10. Commander-zone cards are metadata, not `main_deck` cards.
11. `commander_analysis.json` carries two archetype reads: prefer `analyzer.archetype_support`
    (evidence bands) over the legacy numeric `archetype_fit`; when they disagree, trust the
    analyzer and treat the legacy score as a hint (BUILDER.md §7.0b). `archetype_fit`,
    `commander_tags` and `synergy_tags` are formally DEPRECATED (see the analysis JSON's
    `legacy_deprecations` block; removal planned v0.10) — new reads should use
    `analyzer.archetype_support`, `analyzer.tags` and `analyzer.signals`.

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
deck-gaps (audit vs plan)
validate
fix
explain
final-build
```

Do not skip validation. Do not treat suggestions as automatic includes.

---

## Error Handling

### JSON error contract (parse defensively)

Under `--json-output`, EVERY error is structured JSON — never a rich text panel:

```json
{"error": {"type": "<type>", "message": "..."}}
```

Types: `usage` (bad flag/command, includes did-you-mean), `cli` (click-level),
`validation` (bad input values: unknown --type, empty query, --role synergy),
`environment` (missing database — run `mtg init-data`), `internal` (unexpected crash).

Rules: **check the `"error"` key BEFORE reading `"results"`** — a well-formed error can
otherwise be silently swallowed by a lazy parse. Non-zero exit codes accompany every error.
Not-found card lookups return `{"found": false, "suggestions": [...]}` with FUZZY
suggestions (in-word typos recover: "Krenkooo" → Krenko, Mob Boss) — offer the suggestion
instead of retrying blind variations.

### Bad candidates

If a tool returns bad candidates, do not blindly use them. Report it in Build Feedback.

Examples:

```text
ramp search returning normal lands
card_draw returning unrelated cards
category-counts compressing interaction too aggressively
unknown price cards affecting budget confidence
validation/fill-land mismatch
```
