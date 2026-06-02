# BUILDER

Main operating guide for the MTG Commander deckbuilding agent.

The local `mtg` CLI is the source of truth for card data, legality, prices, search, suggestions, validation, deck-check, export, and final-build saving.

The agent is responsible for judgment: user preference handling, strategy, package planning, card selection, cuts, explanation, and build feedback.

---

## 1. Reading Order

Read these files in order:

```text
BUILDER.md
agents/system.md
agents/user-feedback.md
agents/commander_analyzer.md
agents/theme_detector.md
agents/card_ranker.md
agents/deck_builder.md
agents/deck_fixer.md
agents/deck_explainer.md
```

`BUILDER.md` is the main guide for the agent workflow.

---

## 2. Non-Negotiable Rules

1. Do not invent cards, card text, prices, legality, power, toughness, or color identity.
2. Do not use Commander-illegal cards.
3. Do not use cards outside the commander's color identity.
4. Do not finalize until `mtg validate` passes with no errors.
5. Do not save to `final-builds/` unless validation passes.
6. Do not create helper scripts such as `build_*.py`, `temp_*.py`, or one-off Python scripts.
7. Do not edit source code, seed files, README, `.env`, `.gitignore`, or agent files during normal deckbuilding.
8. Use official CLI commands instead of manual scripts.
9. `synergy` is not a role. Never use `--role synergy`. Use `--synergy` on a real role.
10. Commander-zone cards are metadata, not `main_deck` cards.
11. Category counts and skeletons are guidance, not hard locks.
12. Budget is a maximum constraint, not a spending target.

---

## 3. Allowed Deckbuilding Artifacts

The agent may create/update only these during normal deckbuilding:

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

Forbidden unless explicitly requested:

```text
build_*.py
temp_*.py
one-off helper scripts
src/**/*.py
data/seed/*.json
README.md
BUILDER.md
agents/*.md
.env
.gitignore
```

If a needed CLI feature is missing, continue as far as possible and report the gap in **Build Feedback**.

---

## 4. Command-Zone Model

Commander decks are modeled as:

```text
command-zone cards + main_deck
```

Normal commander:

```text
1 commander + 99 main deck cards = 100 cards
```

Partner/two-command-zone decks:

```text
2 commanders + 98 main deck cards = 100 cards
```

Preferred deck JSON:

```json
{
  "commander": "<Commander>",
  "main_deck": [
    { "name": "Sol Ring", "quantity": 1 }
  ]
}
```

Partner JSON:

```json
{
  "commanders": ["<Commander A>", "<Commander B>"],
  "main_deck": [
    { "name": "Sol Ring", "quantity": 1 }
  ]
}
```

The commander should not be inside `main_deck`. If a flat list contains the commander, validation/fill tools should treat it as command-zone metadata and remove it from the main-deck count.

---

## 5. User Feedback Flow

Default: ask up to **4 core questions** before building. Use multiple choice and always include `Agent choice`.

The 4th question is always:

```text
How much build detail do you want?

a) Quick build — ask only the core questions and then build
b) Detailed build — ask more preference questions before building and clarify during the build when useful
c) Agent choice
```

Detailed build mode may ask about playstyle, speed, theme strictness, ramp, interaction, win style, staples, salt level, budget strictness, pet cards, and exclusions.

Do not ask endless questions. Ask only questions that materially change the deck.

---

## 6. Standard Build Workflow

Use this flow unless the user gives a narrower task:

```bash
mtg commander-analyze --commander "<Commander>" --output output/commander_analysis.json --json-output
```

Partner:

```bash
mtg commander-analyze --commander "<Commander A>" --partner "<Commander B>" --output output/commander_analysis.json --json-output
```

Plan categories:

```bash
mtg category-counts \
  --commander "<Commander>" \
  --archetype "<Archetype>" \
  --power-level <number> \
  --philosophy "<Philosophy>" \
  --analysis output/commander_analysis.json \
  --json-output
```

Optional context:

```bash
mtg explore --commander "<Commander>" --json-output
mtg combos --commander "<Commander>" --output output/commander_combos.json --json-output
```

Build file:

```bash
mtg deck-write \
  --input output/decklist.txt \
  --output output/deck.json \
  --commander "<Commander>" \
  --structured \
  --force
```

Partner:

```bash
mtg deck-write \
  --input output/decklist.txt \
  --output output/deck.json \
  --commander "<Commander A>" \
  --partner "<Commander B>" \
  --structured \
  --force
```

Fill lands:

```bash
mtg deck-fill-lands --deck output/deck.json --commander "<Commander>" --output output/deck.json --force
```

Validate:

```bash
mtg validate --commander "<Commander>" --deck output/deck.json --json-output
```

Run deck-check / budget if applicable, fix errors, explain, then final-build.

---

## 7. Commander Analysis Contract

`output/commander_analysis.json` is the tactical map for the build.

Use it for:

```text
color identity
commander slots / library slots
type line, card types, subtypes, supertypes
power/toughness when available
text signals
commander tags / type tags / synergy tags / anti-synergy tags
engine profile
archetype fit
role pressures
commander scores
provides / requires / rewards
wanted card patterns
avoid card patterns
build direction options
```

Power/toughness is card data. Use it for combat, Voltron, aggro pressure, commander fragility, blocker quality, and creature win-condition evaluation. Do not invent it when missing.

---

## 8. Search Contract

### Simple search

```bash
mtg search "draw a card" --json-output
```

### Structured search string

```bash
mtg search 'type:vampire oracle:draw' --json-output
mtg search 'mv<=3 oracle:draw oracle:card' --json-output
```

Repeated structured tokens use **AND** semantics.

### Cleaner repeatable filters

Prefer repeatable options when the query has quotes/apostrophes:

```bash
mtg search --oracle "can't be blocked" --oracle target --oracle creature --json-output
mtg search --oracle "draw a card" --type creature --json-output
mtg search --card-type vampire --type creature --json-output
mtg search --name Ajani --card-type planeswalker --json-output
mtg search --mv-lte 3 --oracle draw --oracle card --type creature --json-output
```

Repeatable filters use **AND**. A result must match every provided filter.

Available filters:

```text
--oracle / --text   repeatable, searches oracle_text
--name              repeatable, searches card name
--card-type         repeatable, searches type_line
--subtype           repeatable, searches type_line
--mv                exact mana value
--mv-lte            mana value <= number
--mv-gte            mana value >= number
--type              broad type_line filter; also available on search-tags and suggest
```

`type:<value>` inside the query searches type line text, often including subtypes. `--type <value>` is an explicit broad type filter. They can be combined:

```bash
mtg search "type:vampire" --type creature --json-output
```

---

## 9. Suggest Contract

`role` = the functional job/use of the card.

`--synergy` = the card also supports or connects with the given commander.

Examples:

```bash
mtg suggest --commander "<Commander>" --role ramp --json-output
mtg suggest --commander "<Commander>" --role ramp --synergy --json-output
mtg suggest --commander "<Commander>" --role engine --synergy --analysis output/commander_analysis.json --json-output
mtg suggest --commander "<Commander>" --role card_draw --type creature --json-output
```

Rules:

1. Never use `--role synergy`.
2. `--synergy` never replaces role matching.
3. Role match happens first.
4. `--type` narrows results after role match; it never bypasses the role.
5. A role result should have non-empty `matched_tags`.
6. Ramp must be real acceleration: rocks, dorks, rituals, Treasure makers, land search, extra land drops, or meaningful cost reducers.
7. Normal lands are not ramp.
8. Card draw must be actual draw, card advantage, or filtering.
9. Off-role results are tool bugs; do not use them.

---

## 10. Category Counts Contract

Use `category-counts` for package planning.

Use:

```text
recommended_range
need_score
uncompressed_target_count
compressed_target_count
effective_target_count
slot_budget notes
forced_archetype_warning
fit_confidence
```

Rules:

1. Use recommended ranges as planning guidance.
2. Do not treat compressed targets as hard deckbuilding rules.
3. If a forced archetype has low fit, keep the user's choice but apply extra judgment.
4. Do not let slot compression silently remove all interaction or win conditions.
5. Skeletons are fallback guidance only.
6. Landfall/landsmatter should usually target 38–42 lands, not hard-lock exactly 40 unless asked.

---

## 11. Budget Contract

Budget is a maximum constraint, not a spending target.

```text
Deck synergy > spending the full budget.
Under budget is valid.
Default overage allowance is 10%.
Unknown price means unknown, not free and not forbidden.
```

Use:

```bash
mtg budget output/deck.json --budget <amount> --overage 10 --json-output
```

Do not add expensive cards only to spend budget. Optional upgrades can be listed separately.

---

## 12. Explore and Combos Contract

`explore` and `combos` are optional context.

```bash
mtg explore --commander "<Commander>" --json-output
mtg combos --commander "<Commander>" --output output/commander_combos.json --json-output
```

Use combo data for two reasons:

1. If the user wants combos, evaluate compact combo packages.
2. If the user does not want combos, individual combo pieces may still signal useful cards.

Rules:

- Do not force combos into every deck.
- Do not include full combos in low-salt/friendly builds unless requested.
- Do not include high-bracket combos in low-power decks unless requested.
- Combo cards still need legality, color identity, budget, role, and theme checks.

---

## 13. Validation Contract

A deck is not complete until validation passes.

Validation must confirm:

```text
all cards exist
no hallucinated/misspelled names
all cards are Commander legal
all cards fit color identity
singleton rule
correct main deck size
correct total size including command-zone cards
```

If validation fails, fix before any final build.

Common errors:

| Error | Meaning | Action |
|---|---|---|
| `card_not_found` | hallucinated/misspelled card | replace with real card |
| `not_commander_legal` | illegal in Commander | replace |
| `color_identity_violation` | outside commander identity | replace |
| `invalid_deck_size` | wrong main-deck count | add/cut cards |
| `singleton_violation` | duplicate non-basic | remove duplicates |
| `commander_missing` | no commander metadata/flag | pass `--commander` or structured metadata |

---

## 14. Final Build Contract

Final builds go under:

```text
final-builds/<Commander>-<Theme>-<Bracket>-<Version>/
```

Each folder contains:

```text
<build-name>.txt
<build-name>.explanation.md
```

Use:

```bash
mtg final-build \
  --deck output/deck.json \
  --commander "<Commander>" \
  --theme "<Theme>" \
  --bracket T3 \
  --explanation output/deck_explanation.md
```

Never final-build if validation failed.

---

## 15. Build Feedback

Include Build Feedback only when useful.

Good feedback is specific and actionable:

```text
Search friction
Seed/tag gap
Category-count mismatch
Validation issue
Budget uncertainty
Unknown prices
Missing CLI feature
Deck-check limitation
```

If the build went smoothly, do not invent feedback.
