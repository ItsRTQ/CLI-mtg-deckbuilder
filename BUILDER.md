# BUILDER

Main operating guide for the MTG Commander deckbuilding agent.

The local `mtg` CLI is the source of truth for card data, legality, search, suggestions, pricing, validation, deck-check, enrichment, export, and final build saving.

The agent is responsible for deckbuilding judgment: strategy, package planning, card choice, cuts, explanation, and user preference handling.

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

`BUILDER.md` replaces the old `AGENT_USAGE.md`. If an old workflow references `AGENT_USAGE.md`, treat it as a compatibility pointer to this file.

---

## 2. Non-Negotiable Rules

1. Do not invent cards.
2. Do not use cards outside the commander's color identity.
3. Do not use Commander-illegal cards.
4. Do not finalize a deck until `mtg validate` passes with no errors.
5. Do not save anything to `final-builds/` unless validation passes.
6. Do not create helper scripts such as `build_*.py`, `temp_*.py`, or one-off Python scripts.
7. Do not edit source code, seed files, README, `.env`, `.gitignore`, or agent files during normal deckbuilding unless the user explicitly asks.
8. Use official CLI commands for deck creation, land filling, validation, export, and final build.
9. `synergy` is not a role. Never use `--role synergy`. Use `--synergy` as a modifier on a real role.
10. Commander-zone cards must not live inside `main_deck` in structured deck JSON.

Allowed working artifacts:

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

## 3. Core Build Model

Every deck is built from:

```text
Commander + Archetype + Detail + Constraints + User Feedback
```

Use the commander's real engine. Ask:

```text
What does the commander ask for?
What resources does it use?
What events trigger it?
What card types does it prefer?
What protects the engine?
What converts the engine into a win?
```

Do not use commander-specific templates. Use generic archetypes and packages.

---

## 4. User Preference Flow

Use `agents/user-feedback.md` when preferences are missing.

Default: ask up to **4 multiple-choice questions** before deckbuilding. Always include `Agent choice`.

The 4th core question is always:

```text
How much build detail do you want?

a) Quick build — ask only core questions, then build.
b) Detailed build — ask more targeted questions before and during building.
c) Agent choice
```

Quick build: proceed after the 4-question flow and use sensible defaults.

Detailed build: ask additional targeted questions only when they affect construction, such as playstyle, speed, theme commitment, ramp preference, interaction, win style, staples, combo/tutor/salt policy, budget flexibility, pet cards, or exclusions.

Do not ask endless questions. If enough information exists, build.

---

## 5. Standard Build Workflow

Follow this sequence unless the user gives a different instruction.

### Phase A — Gather and analyze

```bash
mtg card "<commander>" --json-output
mtg commander-analyze --commander "<commander>" --output output/commander_analysis.json --json-output
```

Partner commanders:

```bash
mtg commander-analyze --commander "<commander A>" --partner "<commander B>" --output output/commander_analysis.json --json-output
```

Use `output/commander_analysis.json` as the tactical map for category-counts, synergy suggestions, card ranking, and deck explanation.

### Phase B — Plan counts

```bash
mtg category-counts \
  --commander "<commander>" \
  --archetype "<archetype>" \
  --power-level <number> \
  --philosophy "<philosophy>" \
  --analysis output/commander_analysis.json \
  --json-output
```

Partner commanders:

```bash
mtg category-counts \
  --commander "<commander A>" \
  --partner "<commander B>" \
  --archetype "<archetype>" \
  --power-level <number> \
  --philosophy "<philosophy>" \
  --analysis output/commander_analysis.json \
  --json-output
```

Use `recommended_range` and `uncompressed_target_count` for planning. `compressed_target_count` and `target_count` are slot-pressure outputs, not hard locks.

If forced archetype fit is low, respect the user but do not pretend the commander naturally supports that plan.

### Phase C — Search candidates

Structured search examples:

```bash
mtg search "type:demon" --limit 20 --json-output
mtg search "type:creature oracle:draw" --colors UB --limit 20 --json-output
mtg search "mv<=2 type:artifact oracle:Add" --colors WU --limit 20 --json-output
```

Supported lightweight search tokens:

```text
type:<value>
oracle:<value>
text:<value>
name:<value>
mv:<number>
mv<=<number>
mv>=<number>
```

Do not assume full Scryfall syntax.

#### Broad type filter: `--type`

Use `--type` when you want an effect attached to a specific card type:
card draw on creatures, ramp on artifacts, removal on instants, sacrifice
outlets on creatures/artifacts.

```bash
mtg search "draw a card" --type creature --json-output
mtg search "Add" --type artifact --json-output
mtg search "destroy target" --type instant --json-output
mtg search "return target" --type sorcery --json-output
mtg search "landfall" --type enchantment --json-output
```

`--type` filters the broad card type via `type_line` (case-insensitive,
substring). It does NOT replace the `type:<value>` query token — they combine.
`type:<value>` matches any word in the type line (often a subtype like
`vampire`); `--type` is an explicit broad-type filter. Combined:

```bash
mtg search "type:vampire" --type creature --json-output
# type_line contains Vampire AND contains Creature
```

Supported types: `artifact, creature, enchantment, instant, sorcery,
planeswalker, land, battle` (plurals accepted).
Aliases: `spell` (instant/sorcery), `permanent`, `nonland`.

`--type` is also available on `search-tags` and `suggest`:

```bash
mtg search-tags card_draw --type creature --json-output
mtg suggest --commander "<commander>" --role card_draw --type creature --json-output
```

On `suggest`, `--type` is applied AFTER role match — it never bypasses the
role filter (e.g. `--role ramp --type land` still requires a land-ramp tag).

### Phase D — Suggest by role

Role = the card's functional job.

```bash
mtg suggest --commander "<commander>" --role ramp --limit 30 --json-output
mtg suggest --commander "<commander>" --role card_draw --limit 30 --json-output
mtg suggest --commander "<commander>" --role removal --limit 30 --json-output
mtg suggest --commander "<commander>" --role protection --limit 30 --json-output
```

Synergy = the card also connects to the commander.

```bash
mtg suggest --commander "<commander>" --role engine --synergy --analysis output/commander_analysis.json --limit 40 --json-output
mtg suggest --commander "<commander>" --role enabler --synergy --analysis output/commander_analysis.json --limit 40 --json-output
mtg suggest --commander "<commander>" --role payoff --synergy --analysis output/commander_analysis.json --limit 40 --json-output
mtg suggest --commander "<commander>" --role cheap --synergy --analysis output/commander_analysis.json --limit 30 --json-output
```

Never set the role value to `synergy`. That role is invalid. Use a real role plus the `--synergy` flag instead.

`--synergy` never bypasses role matching. Example: `--role ramp --synergy` means the card must be real ramp and also fit the commander.

### Phase E — Optional context commands

Community recommendations:

```bash
mtg explore --commander "<commander>" --json-output
```

Combo context:

```bash
mtg combos --commander "<commander>" --output output/commander_combos.json --json-output
mtg combos --commander "<commander>" --max-bracket 3 --limit 20 --output output/commander_combos.json --json-output
```

These are candidate signals only. They are not mandatory includes.

### Phase F — Write deck, fill lands, validate

Prefer structured deck JSON.

```bash
mtg deck-write \
  --input output/decklist.txt \
  --output output/deck.json \
  --commander "<commander>" \
  --structured \
  --force
```

Partner commanders:

```bash
mtg deck-write \
  --input output/decklist.txt \
  --output output/deck.json \
  --commander "<commander A>" \
  --partner "<commander B>" \
  --structured \
  --force
```

Fill basics:

```bash
mtg deck-fill-lands --deck output/deck.json --commander "<commander>" --output output/deck.json --force
```

Partner commanders:

```bash
mtg deck-fill-lands --deck output/deck.json --commander "<commander A>" --partner "<commander B>" --output output/deck.json --force
```

Validate:

```bash
mtg validate --commander "<commander>" --deck output/deck.json --json-output
```

Partner commanders:

```bash
mtg validate --commander "<commander A>" --partner "<commander B>" --deck output/deck.json --json-output
```

### Phase G — Check, fix, export, final build

```bash
mtg deck-check --commander "<commander>" --deck output/deck.json --json-output
mtg enrich output/deck.json --output output/deck.enriched.json
mtg export output/deck.json --output output/deck.moxfield.txt
```

Final build:

```bash
mtg final-build \
  --deck output/deck.json \
  --commander "<commander>" \
  --theme "<theme>" \
  --bracket T4 \
  --explanation output/deck_explanation.md
```

Partner final build:

```bash
mtg final-build \
  --deck output/deck.json \
  --commander "<commander A>" \
  --partner "<commander B>" \
  --theme "<theme>" \
  --bracket T2 \
  --explanation output/deck_explanation.md
```

---

## 6. Command-Zone Model

| Format | Commander-zone cards | Main deck cards | Total |
|---|---:|---:|---:|
| Single commander | 1 | 99 | 100 |
| Partner commanders | 2 | 98 | 100 |

Commander-zone cards should be stored as metadata in structured deck JSON:

```json
{
  "commander": "Brago, King Eternal",
  "main_deck": []
}
```

Partner example:

```json
{
  "commanders": ["Tymna the Weaver", "Thrasios, Triton Hero"],
  "main_deck": []
}
```

The commander does not need to appear inside `main_deck`. If a commander appears in a flat list, the validator treats it as command-zone metadata and removes it from the main-deck count.

`commander_missing` is only a real issue when no commander is provided by CLI flags or structured metadata.

---

## 7. Validation Contract

A deck is complete only when `mtg validate` passes with no errors.

Validation checks:

| Check | Error type | Fix |
|---|---|---|
| Card exists in DB | `card_not_found` | Replace misspelled/hallucinated card |
| Card is Commander legal | `not_commander_legal` | Remove or swap |
| Commander exists | `commander_not_found` | Fix name |
| Commander is eligible | `invalid_commander` | Use valid commander |
| Commander metadata exists | `commander_missing` | Provide `--commander` or structured metadata |
| Color identity | `color_identity_violation` | Swap card |
| Deck size | `invalid_deck_size` | Add/cut cards |
| Singleton | `singleton_violation` | Remove non-basic duplicates |

Validation output should show:

```json
{
  "valid": true,
  "commanders": ["Brago, King Eternal"],
  "commander_slots": 1,
  "expected_main_deck_size": 99,
  "actual_main_deck_size": 99,
  "total_cards_including_commanders": 100,
  "command_zone_cards_removed_from_main_deck": [],
  "errors": [],
  "warnings": []
}
```

---

## 8. Suggest Contract

Role suggestions must return cards that actually satisfy the role.

Strict roles should not return cards with empty `matched_tags`:

```text
ramp
card_draw
removal
board_wipe
protection
graveyard_hate
countermagic
engine
enabler
payoff
cheap
```

Ramp means real acceleration:

```text
mana rocks
mana dorks
rituals
Treasure makers
land search
put lands onto battlefield
extra land drops
meaningful cost reducers
```

Normal lands that only tap for mana are not ramp.

Card draw means actual draw, card advantage, or filtering. Do not accept unrelated legal cards under `card_draw`.

`--synergy` narrows or boosts after role matching. It never replaces role matching.

Card and suggestion JSON include creature `power` and `toughness` (text, since values
can be non-numeric like `*`; `null` for non-creatures). They are a secondary factor for
combat-relevant roles (`combat`, `voltron`, `go_tall`, `go_wide`, `tribal`, `finisher`,
`win_condition`) and for blocker quality. They never override role fit. Treat missing or
non-numeric P/T as unknown; do not invent values.

---

## 9. Budget Rules

Budget is a maximum constraint, not a spending target.

```text
Deck synergy > spending the full budget.
A strong deck can be far under budget.
Default overage allowance: 10%.
Unknown price = unknown, not free and not forbidden.
```

Use:

```bash
mtg budget output/deck.json --budget <amount> --json-output
mtg prices-batch output/deck.json --json-output
```

Do not add expensive cards just to reach the budget.

If unknown-price cards remain, report partial budget confidence and do not claim exact budget compliance.

---

## 10. Combos, Explore, and Community Data

`explore` and `combos` are optional context.

Use combos when:

1. The user wants combos.
2. You want to identify useful combo-adjacent cards.

Rules:

- Combo data is not mandatory.
- Do not force combos into low-salt/friendly builds.
- Do not include high-bracket combos in low-power decks unless the user asks.
- Combo pieces must pass legality, color identity, budget, role balance, and theme fit.

`explore --json-output` should be strict JSON parseable. If it needs `strict=False`, report a tool bug.

---

## 11. Category-Counts Contract

Use category-counts for package planning, not hard locks.

Important fields:

```text
need_score                  priority of category
recommended_range           preferred planning range
uncompressed_target_count   target before slot pressure
compressed_target_count     result after compression
target_count                final reported target
compression_applied         true if target was reduced
slot_budget                 compression notes and warnings
```

If forced archetype fit is low:

- obey the user if they insist
- keep the warning
- use extra judgment
- consider alternate archetypes
- do not let low-fit compressed targets hide basic deck needs like removal or win conditions

---

## 12. Final Build Structure

Final builds are stored in versioned subdirectories:

```text
final-builds/
└── <Commander>-<Theme>-<Bracket>-<Version>/
    ├── <Commander>-<Theme>-<Bracket>-<Version>.txt
    └── <Commander>-<Theme>-<Bracket>-<Version>.explanation.md
```

Never overwrite an existing final build.

---

## 13. Build Feedback

Build Feedback is optional. Include it only after finishing the deck and only when there was meaningful friction.

Good feedback names the tool issue and the future improvement:

```text
Build Feedback:
- Search friction: ramp suggestions returned lands, so ramp candidates needed manual filtering.
- Validation friction: structured deck output failed validation, so command-zone handling should be aligned.
- Category-count friction: forced low-fit archetype compressed removal too aggressively.
```

Do not invent feedback if the build went smoothly.

---

## 14. Final Response Requirements

Only final after validation passes.

Include:

```text
commander
archetype/detail
power/budget assumptions
validation status
export/final build path
gameplan
package breakdown
win conditions
weaknesses/warnings
optional build feedback
```
