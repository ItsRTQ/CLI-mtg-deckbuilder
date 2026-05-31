# AGENT_USAGE

This project uses a local `mtg` CLI tool plus agent instruction files to build Magic: The Gathering Commander decks.

The `mtg` CLI is the source of truth for card data, legality, candidate search, validation, deck-check, enrichment, and export.

The agent is responsible for deckbuilding judgment.

---

## Recommended Agent File Reading Order

Read these files in order:

```text
agents/system.md
agents/user-feedback.md
agents/commander_analyzer.md
agents/theme_detector.md
agents/card_ranker.md
agents/deck_builder.md
agents/deck_fixer.md
agents/deck_explainer.md
```

---

## Core Build Model

Use:

```text
Commander + Archetype + Detail + Constraints + User Feedback
```

Do not use commander-specific templates.

Build from the commander's actual engine:

```text
What does the commander ask for?
What resources does it use?
What events trigger it?
What card types does it prefer?
What protects the engine?
What wins the game?
```

---

## User Feedback First

If the user request is missing important preferences, use `agents/user-feedback.md`.

Ask only useful multiple-choice questions.

Always include `Agent choice`.

Default maximum: 4 questions before deckbuilding.

The 4th question always asks **Quick build vs Detailed build**:

```text
a) Quick build — ask only core questions, then build.
b) Detailed build — ask more targeted preference questions before and during building.
c) Agent choice
```

Core questions (ask the most useful ones first):

```text
power level
budget
build direction if commander has multiple paths
specific include/exclude cards or effects
combo policy
tutor policy
mana base quality
```

**Quick build:** proceed to deckbuilding after the 4-question flow; use sensible defaults for unasked preferences.

**Detailed build:** ask additional targeted questions (playstyle, speed, theme commitment, ramp preference, interaction, win style, staples, table friendliness, budget flexibility); may also ask small clarifying questions during the build when a real decision point appears.

If the user does not answer, choose a reasonable option and continue.

---

## CLI Workflow

Typical commands:

```bash
mtg card "<commander>" --json-output
# Commander analysis — run first to build the shared tactical map
mtg commander-analyze --commander "<commander>" --output output/commander_analysis.json --json-output
mtg commander-analyze --commander "<commander A>" --partner "<commander B>" --output output/commander_analysis.json --json-output
# Structured search (type:, oracle:, name:, mv: tokens)
mtg search "type:demon" --limit 20 --json-output
mtg search "type:creature oracle:draw" --colors UB --limit 20 --json-output
mtg search "mv<=2 type:artifact oracle:Add" --colors WU --limit 20 --json-output
mtg search "<query>" --colors "<colors>" --limit 30 --json-output
# role = functional job of the card
mtg suggest --commander "<commander>" --role ramp --limit 30 --json-output
mtg suggest --commander "<commander>" --role card_draw --limit 30 --json-output
mtg suggest --commander "<commander>" --role removal --limit 30 --json-output
mtg suggest --commander "<commander>" --role protection --limit 30 --json-output
# --synergy narrows role results to cards that also connect with the commander's strategy
# --role synergy is INVALID — use --synergy as a modifier flag instead
# Provide --analysis to use commander_analysis.json for richer synergy signals
mtg suggest --commander "<commander>" --role engine --synergy --analysis output/commander_analysis.json --limit 40 --json-output
mtg suggest --commander "<commander>" --role enabler --synergy --analysis output/commander_analysis.json --limit 40 --json-output
mtg suggest --commander "<commander>" --role payoff --synergy --analysis output/commander_analysis.json --limit 40 --json-output
mtg suggest-lands --commander "<commander>" --count <count> --json-output
# Deck file creation
mtg deck-write --input output/decklist.txt --output output/deck.json --force
mtg deck-fill-lands --deck output/deck.json --commander "<commander>" --output output/deck.json --force
mtg deck-fill-lands --deck output/deck.json --commander "<commander>" --dry-run --json-output
# category-counts: pass --analysis for richer commander scoring
mtg category-counts --commander "<commander>" --archetype <archetype> --power-level <number> --philosophy balanced --analysis output/commander_analysis.json --json-output
mtg category-counts --commander "<commander>" --partner "<partner>" --archetype voltron --power-level 6 --philosophy combat_pressure --json-output
mtg validate --commander "<commander>" --deck output/deck.json --json-output
mtg deck-check --commander "<commander>" --deck output/deck.json --json-output
mtg enrich output/deck.json --output output/deck.enriched.json
mtg export output/deck.json --output output/deck.moxfield.txt
mtg explore --commander "<commander>" --json-output
mtg final-build --deck output/deck.json --commander "<commander>" --theme "<theme>" --bracket T4
# Partner decks:
mtg validate --commander "Tymna the Weaver" --partner "Thrasios, Triton Hero" --deck output/deck.json
mtg deck-fill-lands --deck output/deck.json --commander "Tymna the Weaver" --partner "Thrasios, Triton Hero" --output output/deck.json --force
mtg final-build --deck output/deck.json --commander "Tymna the Weaver" --partner "Thrasios, Triton Hero" --theme "Goodstuff" --bracket T2
```

If package-aware commands exist, prefer them. If not, use `search` and normal `suggest` to approximate package searches.

---

## Single vs Partner Commander Decks

| Format | Commanders | Main Deck Cards | Total |
|---|---|---|---|
| Normal | 1 | 99 | 100 |
| Partner | 2 | 98 | 100 |

For partner decks:
- Both commanders must be present in the deck list
- Color identity = **combined** color identity of both commanders
- All 98 main deck cards must fit within the combined identity
- Build around **both** commanders' strategies
- Analyze what both commanders share (e.g. color synergy, mechanic overlap, shared trigger conditions)

CLI partner flags:
```bash
--partner "Partner Commander Name"
```

Supported on: `validate`, `final-build`

---

## Output Directories

| Directory | Purpose |
|---|---|
| `output/` | Working files: deck.json, deck.enriched.json, validation_report.json, etc. |
| `final-builds/` | Finalized, validated Moxfield decklists only. Never overwritten. |

**Never save to `final-builds/` unless validation passes.**

---

## Validation Requirements

A deck is not complete until `mtg validate` passes with **no errors**.

Do not save to `final-builds/` if validation fails.

If validation reports a missing card, treat it as a hallucination or misspelling and replace it with a real card from the local database.

### What validation checks

| Check | Error type | Action |
|---|---|---|
| Card exists in local DB | `card_not_found` | Replace with real card |
| Card is Commander legal | `not_commander_legal` | Remove or swap card |
| Commander exists in DB | `commander_not_found` | Fix commander name |
| Commander is eligible | `invalid_commander` | Use a valid commander |
| Commander in deck list | `commander_missing` | Add commander to deck |
| Card fits color identity | `color_identity_violation` | Remove or swap card |
| Deck has correct card count | `invalid_deck_size` | Add or remove cards |
| No non-basic duplicates | `singleton_violation` | Remove extra copies |

### Deck size rules

| Format | Commander slots | Main deck | Total |
|---|---|---|---|
| Single commander | 1 | 99 | 100 |
| Partner commanders | 2 | 98 | 100 |

The validator counts **quantities**, not entries. `{ "name": "Forest", "quantity": 10 }` counts as 10 cards.

### Validation output fields

```json
{
  "valid": true,
  "commander": "Brago, King Eternal",
  "partner": null,
  "commander_slots": 1,
  "expected_main_deck_size": 99,
  "actual_main_deck_size": 99,
  "total_cards_including_commanders": 100,
  "errors": [],
  "warnings": []
}
```

### final-build validation gate

`mtg final-build` runs validation automatically before saving anything. If validation fails:

- No directory is created in `final-builds/`
- No `.txt` or `.explanation.md` is written
- Error list is returned

Only after `"validated": true` does the final build folder get created.

---


## Deck File Creation and Land Filling

Do not create temporary Python scripts such as `build_<commander>.py`, `temp_deck.py`, or one-off helper scripts to generate deck files or fill lands.

Use the official CLI workflow:

1. Write a plain decklist to `output/decklist.txt` (one card per line).
2. Convert it to JSON:

```bash
mtg deck-write --input output/decklist.txt --output output/deck.json --force
```

3. Fill missing basic lands:

```bash
mtg deck-fill-lands --deck output/deck.json --commander "<Commander>" --output output/deck.json --force
```

4. Validate:

```bash
mtg validate --commander "<Commander>" --deck output/deck.json --json-output
```

### deck-write input formats

```text
1 Sol Ring
1x Sol Ring
Sol Ring        (quantity defaults to 1)
# Ramp          (comment — skipped)
## Lands        (section header — skipped)
```

### deck-fill-lands behavior

- Fills remaining slots with basic lands based on commander color identity.
- Does NOT remove cards. If deck is over target, returns an error instead.
- Dry-run mode: `--dry-run` shows what would be added without writing.
- Target defaults to 99 (single commander) or 98 (partner commanders).
- For a deck with an exact target size, no lands are added.

```bash
mtg deck-fill-lands --deck output/deck.json --commander "Be'lakor, the Dark Master" --dry-run --json-output
mtg deck-fill-lands --deck output/deck.json --commander "Be'lakor, the Dark Master" --output output/deck.json --force
```

---

## Search Token Syntax

`mtg search` supports simple structured tokens in addition to plain free-text:

```text
type:<value>    → match type_line (e.g. type:demon, type:artifact)
oracle:<value>  → match oracle_text (e.g. oracle:draw, oracle:sacrifice)
text:<value>    → alias for oracle:
name:<value>    → match card name (e.g. name:ring)
mv:<n>          → exact mana value (e.g. mv:3)
mv<=<n>         → mana value ≤ n (e.g. mv<=2)
mv>=<n>         → mana value ≥ n (e.g. mv>=4)
```

Examples:

```bash
mtg search "type:demon" --limit 20 --json-output
mtg search "type:creature oracle:draw" --colors UB --limit 20 --json-output
mtg search "mv<=2 type:artifact oracle:Add" --colors WU --limit 20 --json-output
mtg search "type:demon sacrifice" --json-output   # free text mixed with token
```

All tokens are AND'd: every token must match for a card to appear.
Unrecognized tokens (e.g. `color:red`) fall back to free-text search.
Plain searches like `mtg search "Sol Ring"` still work as before.

---

## File Editing Boundaries

During normal deckbuilding, the agent should avoid creating, editing, or deleting project files that are not part of the deck being built.

The agent may create or update deck-build artifacts only, such as:

```text
output/decklist.txt
output/deck.json
output/deck.enriched.json
output/deck.moxfield.txt
output/deck_explanation.md
output/validation_report.json
final-builds/<commander>-<theme>-<bracket>-<version>/
final-builds/<commander>-<theme>-<bracket>-<version>/<name>.txt
final-builds/<commander>-<theme>-<bracket>-<version>/<name>.explanation.md
```

The agent should not modify these project files during a normal deck build unless the user explicitly asks for implementation work:

```text
README.md
AGENT_USAGE.md
agents/*.md
data/seed/*.json
src/**/*.py
tests/*
requirements.txt
pyproject.toml
.env
.gitignore
```

**Forbidden during normal deckbuilding unless explicitly requested:**

```text
build_*.py
temp_*.py
one-off Python helper scripts in the project root
project source code edits
seed data edits
agent instruction file edits
```

If the agent discovers that the CLI, tags, search, suggestions, validation, pricing, or seed files need improvement, it should not silently edit those files during deckbuilding. It should finish the deck as well as possible and report the issue in the optional build feedback section.

If the CLI lacks a command needed for deck creation, finish as far as possible and report the missing command in Build Feedback instead of creating a helper script.

Do not create random scratch files in the project root. If a temporary file is necessary, place it under `output/` and prefer CLI-supported cleanup commands such as:

```bash
mtg temp-clean
mtg temp-clean --full --yes
```

Deckbuilding permission rule:

```text
Allowed: create/update files needed to build, validate, export, explain, or finalize the current deck.
Not allowed by default: edit the project, source code, config, agent instructions, seed data, or dependency files.
```

---
## Final Build Command

After a deck is complete and passes validation, save it as a versioned final build folder:

```bash
mtg final-build \
  --deck output/deck.json \
  --commander "Edgar Markov" \
  --theme "Tribal" \
  --bracket T4 \
  --explanation output/deck_explanation.md
```

If `--explanation` is omitted, the command automatically uses `output/deck_explanation.md` if it exists, otherwise generates a minimal stub.

Or using a power level label instead of bracket:

```bash
mtg final-build \
  --deck output/deck.json \
  --commander "Edgar Markov" \
  --theme "Tribal" \
  --power-level casual \
  --explanation output/deck_explanation.md
```

Bracket mapping:

| Power Label | Bracket |
|---|---|
| competitive, cedh | T1 |
| highly_optimized, high_power | T2 |
| optimized_casual, precon_optimized | T3 |
| casual, precon, precon_level | T4 |

Final builds are saved into versioned sub-directories:

```text
final-builds/
└── Edgar-Markov-Tribal-T4-v1/
    ├── Edgar-Markov-Tribal-T4-v1.txt
    └── Edgar-Markov-Tribal-T4-v1.explanation.md
```

Versioning checks sub-directory names. Old builds are never overwritten. Final builds use simple Moxfield format (`1 Card Name`) with no set codes or collector numbers.

Example for a commander with apostrophe:

```text
final-builds/
└── Caesar-Legions-Emperor-Mardu-Tokens-Aristocrats-T3-v1/
    ├── Caesar-Legions-Emperor-Mardu-Tokens-Aristocrats-T3-v1.txt
    └── Caesar-Legions-Emperor-Mardu-Tokens-Aristocrats-T3-v1.explanation.md
```

Always pass `--explanation output/deck_explanation.md` after writing the explanation. If the file does not exist, a minimal stub is generated automatically.

---

## Role Guide: ramp vs cheap

### ramp

Use `ramp` only for cards that clearly accelerate mana:

```text
mana rocks ({T}: Add ...)
mana dorks ({T}: Add {G} etc.)
land ramp (search library for a land, put a land onto the battlefield)
treasure makers (create a Treasure token)
rituals (Add {B}{B}{B} etc.)
extra land drops (play an additional land)
cost reducers (spells cost less to cast)
```

`ramp` has `requires_tag_match = true`. Cards with no matched ramp tag are excluded regardless of mana value.

Low mana value alone never qualifies a card as ramp.

If `suggest --role ramp` returns cards with `"matched_tags": []`, treat that as a tool problem and do not use those cards.

### cheap

Use `cheap` for low-cost synergistic cards (mana_value ≤ 3) that support the commander engine, archetype, or theme.

`cheap` is different from ramp:
- ETB effects (for blink/flicker)
- Cheap protection
- Cheap removal
- Cheap enablers (sacrifice outlet, token maker)
- Cheap draw
- Cheap equipment or aura
- Cheap haste / evasion

`cheap` also requires at least one synergy tag match. Do not include cards only because they are cheap.

```bash
mtg suggest --commander "Brago, King Eternal" --role cheap --limit 10 --json-output
```

---

## Batch Card and Price Lookups

Use batch commands to reduce tool calls when checking many cards:

```bash
# Look up multiple cards at once
mtg cards "Sol Ring" "Arcane Signet" "Not A Real Card" --json-output

# Look up prices for multiple cards
mtg prices "Sol Ring" "Arcane Signet" "Not A Real Card" --json-output

# Look up all cards in a deck file
mtg cards-batch output/deck.json --json-output

# Look up prices for all cards in a deck file
mtg prices-batch output/deck.json --json-output
```

Not-found cards are included in results with `"found": false`. The commands never crash on a missing card.

---

## Validator: Flat and Structured Deck JSON

The validator accepts both formats:

**Flat list (original format):**
```json
[{ "quantity": 1, "name": "Sol Ring" }]
```

**Structured (new format):**
```json
{
  "commander": "Brago, King Eternal",
  "main_deck": [{ "quantity": 1, "name": "Sol Ring" }]
}
```

**Partner commanders:**
```json
{
  "commanders": ["Tymna the Weaver", "Thrasios, Triton Hero"],
  "main_deck": [{ "quantity": 1, "name": "Sol Ring" }]
}
```

CLI flags (`--commander`, `--partner`) always take precedence over file-embedded commander metadata.

---

## Pricing and Budget

Price data comes from the local Scryfall database. Do not search the web for card prices during deckbuilding.

```bash
mtg price "Sol Ring" --json-output
mtg budget output/deck.json --json-output
mtg budget output/deck.json --budget 500 --json-output
mtg budget output/deck.json --budget 500 --overage 10 --json-output
mtg budget output/deck.json --budget 500 --overage 0 --json-output
mtg budget output/deck.json --strict --json-output  # fail if any price is unknown
```

### Budget is a maximum, not a target

**Budget is a ceiling, not a goal. The deck does not need to spend the full budget.**

Priority order for card selection:

```text
1. Card legality
2. Color identity
3. Commander/deck synergy
4. Role/package need
5. Power level fit
6. Budget fit
7. Price efficiency
```

Do not add expensive cards just to get closer to the user's budget. If the deck is legal, synergistic, coherent, and under budget, keep it under budget.

A deck costing $280 on a $500 budget is **valid and often better** than spending $480 on staples that don't fit the commander engine.

### Budget status categories

| Status | Meaning |
|---|---|
| `under_budget` | Known total ≤ budget limit. Valid, no action needed. |
| `within_overage` | Known total > limit but ≤ limit × (1 + overage%). Acceptable. |
| `over_budget` | Known total > hard limit. Reduce cost by replacing expensive low-synergy cards. |

Default overage is 10%. A $500 budget allows up to $550 by default.

When a deck is over budget, replace expensive low-synergy cards first. Preserve key engine pieces, synergy cards, and role balance.

When a deck is under budget, optional upgrades may be suggested separately but must not be automatically applied unless the user asks.

### Price rules

- `usd_price` is the primary budget field.
- `price_status = "unknown"` means price data is missing, not that the card is free.
- Unknown-price cards are allowed by default.
- Do not treat unknown price as $0 when estimating budget.
- `budget_confidence = "complete"` only when all non-basic-land cards have known USD price.
- `budget_confidence = "partial"` when any card has unknown price.

### Budget deckbuilding rules

- For budget decks, use `mtg budget --budget <amount>` for price totals. Do not estimate prices manually.
- Cards with missing USD price may still be strong candidates — report them, do not exclude them.
- Basic lands (Plains, Island, Swamp, Mountain, Forest, Wastes) are treated as free.
- Only exclude unknown-price cards if the user explicitly requests `--strict` budget mode.
- When reporting budget: list unknown-price cards and note `budget_confidence = "partial"`.
- Never claim exact budget compliance when unknown-price cards remain in the deck.
- Do not add expensive cards to close the gap between actual cost and the budget limit.

---

## Community Recommendations: explore command

The `explore` command fetches community card data for a commander from EDHREC.

```bash
mtg explore --commander "Omnath, Locus of Rage" --json-output
```

Output shape:

```json
{
  "commander": "Omnath, Locus of Rage",
  "source_url": "...",
  "high_synergy": [{"name": "...", "found_in_database": true, "commander_legal": true, "color_identity": []}],
  "top_cards": [...],
  "note": "Community recommendations only. These are candidates, not mandatory includes."
}
```

### How to use explore output

- Use `high_synergy` and `top_cards` as **additional candidates** during card ranking.
- Treat them as **community signal** — popular choices that often work well.
- Cross-reference against your package plan and role analysis.
- Run each candidate through `mtg card "<name>" --json-output` if you need full gameplay data.

### What explore output is NOT

- Not an auto-include list.
- Not a replacement for role balance (ramp, draw, removal, protection).
- Not a replacement for color identity or legality checks.
- Not a replacement for commander engine analysis.
- Not authoritative — community data can include suboptimal, budget-unfriendly, or meta-specific choices.

If a community recommendation conflicts with user constraints (budget, power level, theme), ignore it.

---

## Category-Count Recommendations

Use `mtg category-counts` to get soft target ranges for each category before building.

```bash
mtg category-counts \
  --commander "Teysa Karlov" \
  --archetype aristocrats \
  --power-level 6 \
  --philosophy balanced \
  --json-output

mtg category-counts \
  --commander "Ardenn, Intrepid Archaeologist" \
  --partner "Rograkh, Son of Rohgahh" \
  --archetype voltron \
  --power-level 6 \
  --philosophy combat_pressure \
  --json-output
```

Optional flags:
- `--meta <meta>` — e.g. `creature_heavy`, `graveyard_heavy`, `combo_heavy`, `fast_high_power`
- `--projected-average-mv <float>` — refine land and ramp estimates
- `--bracket T1/T2/T3/T4` — alternative to `--power-level`

### category-counts output rules

- `need_score`: How important this category is (0–10). Use this to judge priority even if `target_count` was compressed.
- `target_count`: Final count after slot-budget compression. May be below the `recommended_range` if total demand exceeds available nonland slots.
- `recommended_range`: Ideal range before compression. Use this as the agent's planning target.
- `slot_budget.compression_needed`: If `true`, compression notes explain what was reduced.
- `multi_tag_policy`: A card may count toward multiple categories but uses one physical slot. Do not assume 100% coverage for each category independently.

**Category-count output is soft guidance — not a hard lock.** User constraints, synergy judgment, and actual card availability override it. If the output shows unrealistic slot pressure or poor recommendations, include it in Build Feedback.

---

## Required Build Steps

1. Parse user request.
2. Ask user-feedback questions if useful.
3. Look up commander with CLI.
4. Confirm legality and commander eligibility.
5. Analyze commander engine.
6. Detect archetype/detail/constraints.
7. Run `mtg category-counts` to get package count targets.
8. Use `need_score` and `recommended_range` to plan package sizes.
9. Search candidates by role and package.
10. Rank candidates.
11. Build 100-card deck using count targets as guidance.
12. Write plain decklist to `output/decklist.txt`, then convert with `mtg deck-write --input output/decklist.txt --output output/deck.json --force`, then fill basic lands with `mtg deck-fill-lands --deck output/deck.json --commander "<commander>" --output output/deck.json --force`.
13. Validate.
14. Fix errors.
15. Run deck-check.
16. Fix major coherence issues.
17. Export only after validation passes.
18. Explain deck.
19. If the build had meaningful friction (including poor category-counts recommendations), include optional build feedback.

---

## Generic Deckbuilding Defaults

### Lands

Calculate after nonlands:

```text
base 32
+1 per commander color, max +3
+0 if avg MV 0.0–2.6
+1 if avg MV 2.7–3.3
+2 if avg MV 3.4+
```

Landfall/landsmatter:

```text
38–42 lands
```

### Ramp

```text
9 minimum
```

Prefer at least 5 rocks when appropriate, including Sol Ring and Arcane Signet unless user/theme/budget says otherwise.

### Draw

Tutors are search, not draw.

Increase draw for low-curve, spell-heavy, or hand-emptying decks.

### Removal

```text
5–15 total interaction/removal
spot removal: 2–4
board wipes: 1 default, 3 max
artifact/enchantment removal: 0–2
graveyard hate: 0–1 unless meta requires more
```

### Protection

```text
0–5 default
```

Increase when commander is central, must attack/connect, or deck fails without it.

### Win Conditions

```text
1–5 win paths
```

Explain each win path clearly.

---

## Power Brackets

```text
Casual = precon/precon-level, no infinite combos, no tutors by default
Optimized Casual = upgraded precon, 1–2 tutors if useful, no infinite combos, medium+ synergy
High Power = high synergy, tutors allowed, 1–2 incidental combos allowed
cEDH = no budget by default, best legal options, unrestricted combos/tutors
```

---


## Optional Build Feedback

At the end of a deck build, include a short feedback section only if the build had meaningful friction, uncertainty, or tool limitations.

This feedback is not mandatory. If the build went smoothly, skip it.

Use this section to help improve future builds. Be specific and actionable.

Good feedback examples:

```text
Build Feedback:
- Search friction: `suggest --role ramp` returned cards with empty matched_tags, so ramp candidates needed extra manual filtering.
- Tag gap: Brago blink support would improve if `etb`, `blink`, and `mana_rock` tags were stronger.
- Pricing issue: Several cards had unknown prices, so budget confidence is partial.
- Validation friction: Partner commander support required manual size checking for 98 main deck cards.
```

Avoid vague feedback:

```text
The tool could be better.
The deck was hard.
Search was bad.
```

Feedback should answer:

```text
What was hard to set up?
What tool behavior slowed down the build?
What data was missing or unreliable?
What specific future improvement would help? Examples: better search, better suggestions, better tags, better role definitions, better price coverage, better validation messages.
```

Do not use build feedback as an excuse to skip the deck. Finish the deck first, then report improvement points if needed.

---
## Final Output

Only final after validation passes.

Include:

- deck export path
- commander
- archetype/detail
- power/budget assumptions
- validation status
- gameplan
- package breakdown
- win conditions
- weaknesses/warnings
- optional build feedback, only if the build had meaningful friction
