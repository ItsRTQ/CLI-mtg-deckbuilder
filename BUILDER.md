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

`$.venv/bin/mtg` is how you will use the mtg tool

`$.venv/bin/mtg --help` is how you will see the possible commands for the mtg tool

`$.venv/bin/mtg <command> --help` is how you will see specific instructions for a command(use this to take full advantage of the mtg tool)

---

## 2. Non-Negotiable Rules

1. Do not invent cards, card text, prices, legality, power, toughness, or color identity.
2. Do not use Commander-illegal cards.
3. Do not use cards outside the commander's color identity.
4. Do not finalize until `mtg validate` passes with no errors.
5. Do not save to `final-builds/` unless validation passes.
6. Do not create helper scripts such as `build_*.py`, `temp_*.py`, or one-off Python scripts that *generate, assemble, or decide* the deck. This rule is about not bypassing the CLI's logic — it does **not** forbid read-only inspection of CLI output (e.g. piping `--json-output` through `jq`/`python -m json.tool` to filter or pretty-print, or counting results). Reading and reformatting the CLI's output is fine; producing or editing deck content outside the CLI is not — to change a card in the list use `mtg deck-swap` (it validates before writing), never a `sed`/`python` replace.
7. Do not edit source code, seed files, README, `.env`, `.gitignore`, or agent files during normal deckbuilding.
8. Use official CLI commands instead of manual scripts.
9. `synergy` is not a role. Never use `--role synergy`. Use `--synergy` on a real role.
10. Commander-zone cards are metadata, not `main_deck` cards.
11. Category counts and skeletons are guidance, not hard locks.
12. Budget is a maximum constraint, not a spending target.
13. Before starting the build ask the user "Do you want to clear output folder? "(Yes/No - answere only) if user selects yes run(.venv/bin/mtg temp-clean --full --yes) to clear output folder using the mtg tool. if user select no, then skip and continue to build

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

**MANDATORY STEP — verify the drafted list BEFORE building** (catches misspelled/hallucinated/
illegal names cheaply, before the deck-write → fill → validate cycle; the Gargos and Anowon test
builds each caught invented card names here). A build that skips this step is not following this
document. `cards-batch`, `prices-batch`, and `budget` accept the
plain-text `output/decklist.txt` directly — no need to convert to JSON first:

```bash
mtg cards-batch output/decklist.txt --verify
```

`--verify` reports only the names that weren't found (with suggestions) and exits non-zero if any
are missing — use it instead of piping `--json-output` through a script to find `"found": false`.

Other built-in helpers so you never need an inline `python`/`jq` script to read or edit:

```bash
mtg card "<Card>" --field oracle_text          # one raw field, no JSON/grep needed
mtg category-counts ... --table                # flat one-row-per-category table, sorted by need
mtg budget output/decklist.txt --budget <USD> --by-card   # total + most-expensive cards + high-cost flags
mtg deck-swap --deck output/decklist.txt --commander "<Commander>" --swap "Old=New"
```

`deck-swap` is the blessed way to change a card in the list (budget trim, swap a salt card, etc.):
it validates the incoming card (exists, Commander-legal, in color identity, no singleton dup)
**before writing** and aborts atomically if anything is wrong — never hand-edit the decklist with a
`sed`/`python` replace, which skips all those checks.

For double-faced/split cards, the front-face name resolves (e.g. `Valakut Awakening`).

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

Finalization gate — REQUIRED before declaring the deck done or running `final-build`:

```bash
mtg preflight --deck output/deck.json --commander "<Commander>" [--budget <USD>]
```

`preflight` runs every must-pass check in one shot (commander legal & in the command zone,
deck size, all cards exist, all Commander-legal, singleton, color identity, and budget if given)
and prints a checklist ending in `READY` or `NOT READY` (exit code 0/1). Do not finalize unless it
prints `READY`. This is the single gate that replaces remembering each rule individually — if any
line shows `✗`, fix it and re-run preflight.

Budget Upgrade Review flow (see Section 11):

```text
1. Build initial deck.
2. Validate.
3. Deck-check.
4. Budget-check.
5. If under budget threshold, run Budget Upgrade Review.
6. Show under-budget upgrades and optional over-budget high-impact upgrades.
7. Ask user what to apply.
8. Apply selected upgrades.
9. Re-run validate, deck-check, and budget-check.
10. Final-build only after user decision and passing validation.
```

---

## 7. Commander Analysis Contract

### 7.0b Archetype: prefer `analyzer.archetype_support` over `archetype_fit`

`commander_analysis.json` now carries TWO archetype reads:

- **`analyzer` (preferred)** — the evidence-first analyzer: `archetype_support` as ordinal bands
  (`very_high/high/medium/low`), plus `signals` (detected feature IDs), `dominant_symmetry`, and
  `warnings`. Every band is backed by detected evidence; run `mtg analyze-card "<Commander>"` if
  you need the full traces (which rule fired on which text).
- **`archetype_fit` (legacy)** — weighted text scores. Kept for compatibility during the migration;
  its numeric scores can be confidently wrong (e.g. reminder text once read as a lands/mill plan).

**Rule: when the two disagree, trust `analyzer.archetype_support`.** Treat `archetype_fit` as a
secondary hint at most. **Toolbox commanders:** if `archetype_support` includes `Toolbox / Goodstuff` (or the analyzer
warns "multi-mode commander"), the per-mode bands are OPTIONS on a menu, not the theme. Resolve
the menu with the user's answers from the build questions (§5 User Feedback Flow): pick the mode
that best aligns with their requested direction (user wants aggro -> the aggro-adjacent mode).
If their answers don't disambiguate, ASK before committing to a mode.

If `archetype_support` is empty or all-low while the commander clearly has
a plan, that is an analyzer coverage gap — note it (it is calibration signal), reason from the
oracle text yourself, and proceed with your own judgment.


### 7.0 Commander legality pre-check (do this FIRST)

Before analyzing or building, confirm the commander is actually a legal commander:

```bash
mtg card "<Commander>" --field can_be_commander
```

- `True` → proceed normally.
- `False` → the tool's detection may be incomplete. The `can_be_commander` flag is a text/type
  heuristic (Legendary Creature, or "can be your commander" text, or the curated allowlist in
  `data/seed/commander_overrides.json`). It cannot detect non-creature face commanders that carry no
  oracle signal (e.g. some Legendary Vehicles like Shorikai). **Do not silently proceed and do not
  guess.** Instead:
  1. If it's a Legendary Creature or plainly a designated commander, verify quickly via web search
     whether it's a legal Commander (Scryfall/official). If confirmed legal, add its exact name to
     `data/seed/commander_overrides.json` and re-run the check.
  2. If web access is unavailable or the result is ambiguous, ask the user to confirm the commander
     is legal before continuing.
  Only build once legality is confirmed. A wrong allowlist entry would let a non-commander through,
  so add names only when verified.


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
oracle hooks (general, commander-agnostic)
build direction options
```

Power/toughness is card data. Use it for combat, Voltron, aggro pressure, commander fragility, blocker quality, and creature win-condition evaluation. Do not invent it when missing.

The `oracle_hooks` field is derived directly from the commander's oracle text and applies to ANY
commander. Read it before drafting — it captures things the fixed archetype list can miss:
- `named_counters`: the actual counter type(s). If it's a custom counter (e.g. `slime`,
  `experience`), use proliferate and payoffs that count counters of ANY kind, and do NOT include
  +1/+1-specific payoffs — they do nothing. Only treat +1/+1 / -1/-1 payoffs as live if those are
  the listed counters.
- `asymmetric_punisher`: if true, the commander harms opponents' boards; build attrition and
  protection, not go-wide (your own board is not the payoff).
- `trigger_events`, `token_types`, `cost_reduction_type`: the build's natural hooks.
- `build_signals`: a ready-made shopping list derived from the above; it is also merged into
  `wanted_card_patterns`.

---

## 7.9 Audit trail (`--log` / `report`)

Any `mtg` command accepts a global `--log` flag: it appends `{seq, command, full_command,
response, timestamp, exit_code}` to an on-going staging log. `mtg report --name <name> [--note
"<finding>"]... [--summary]` consolidates it into `logs/<name>.json` and clears staging. Use it
when a build should be auditable/reproducible (calibration runs per CALIMAX.md always log; normal
builds may). The log is self-verifying: any logged command can be re-run later and compared.

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

### Search by FUNCTION with tags — go deeper than the obvious

When you want cards that perform a strategic function, reason in **tags** (the tool's vocabulary of
card functions) and let `search-tags` union their phrases and **rank** results by how many facets
each card hits:

```bash
mtg search-tags evasion --colors G --type creature --json-output
mtg search-tags sacrifice_outlet death_trigger --colors B --json-output   # union of several tags
mtg search-tags --list-tags        # all 97 functional tags
```

This is how to go deeper than the obvious without enumerating combinations: decompose the build's
plan into functions (e.g. commander damage = `evasion` + `damage_multiplier` + `protection`;
aristocrats = `sacrifice_outlet` + `death_trigger` + `token_maker`), pull a ranked shortlist per
function, then judge fit against the deck's intent. Each result carries `tag_match_count` (how many
of the requested tags' phrases it hit) — higher = more on-function. Tags are curated and
substring-based, so treat the shortlist as candidates to evaluate, not a verdict, and combine with
`--colors`, `--type`, `--mv-lte`, and `--max-price` to stay inside the build's constraints.

### More search axes

- **Creature stat quality** — `mtg search --pow-gte 5 --mv-lte 4 --colors G --type creature` finds
  efficient beaters. Also `--pow-lte/--tou-gte/--tou-lte`. Variable/`*` power never matches a
  numeric bound (a `*/*` creature is not a guaranteed 5-power beater).
- **By trigger event** — `mtg search --trigger attacks_or_combat --colors R` finds cards that
  trigger on an event family (`--list-triggers`: permanent_dies, permanent_enters, you_cast_spell,
  attacks_or_combat, sacrifice, targeted_by_spell, draw_or_discard, life_change, recurring_tick).
- **Similar / complementary to a card** — `mtg similar "<Card>"` returns cards performing the same
  function (ranked by shared facets); `mtg complements "<Card>"` returns the other half of the
  interaction (a sacrifice outlet → death-triggers, recursion, token makers; a +1/+1 placer →
  proliferate and counter payoffs). Both default to the card's own color identity.

### Auditing the built deck — `deck-gaps`

```bash
mtg deck-gaps --deck output/deck.json --commander "<Commander>" --archetype <archetype>
```

Cross-references the category-count targets and the commander's oracle hooks against what the deck
actually contains, and lists what's thin (ranked by need) with a ready `search-tags` command to fill
each gap — plus hook-specific gaps (e.g. a custom-counter commander with no proliferate). Run it
before finalizing to catch the deck's blind spots against its own plan.

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
2. **`recommended_range` and `need_score` are the source of truth — not `compressed_target_count`.** The compressed target is the most visually prominent number but the least reliable: a Critical/High `need_score` category can be compressed to a tiny target (e.g. payoffs at `need_score` 8.6 compressed to `target_count: 2`). Never build to the compressed target alone. If `need_score` is High/Critical, stay near the **top** of `recommended_range` regardless of the compressed number.
3. Do not treat compressed targets as hard deckbuilding rules.
4. If a forced archetype has low fit, keep the user's choice but apply extra judgment.
5. Do not let slot compression silently remove all interaction or win conditions.
6. Skeletons are fallback guidance only.
7. Landfall/landsmatter should usually target 38–42 lands, not hard-lock exactly 40 unless asked.

---

## 11. Budget Contract

Budget is a maximum constraint, not a spending target.

Budget is also a preference boundary. Some users have a hard budget and cannot go over. Others are fine going over if the upgrade gives major value to the gameplan, win condition, engine, ramp, commander protection, or consistency.

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

### Budget Tolerance Modes

Classify the user's budget tolerance during feedback or Budget Upgrade Review.

```text
hard_budget          - never exceed the stated budget.
soft_budget          - up to default 10% over is okay if the upgrade is meaningful.
value_based_overage  - over budget okay only for major upgrades (gameplan, win
                       condition, engine, ramp, mana base, commander protection,
                       card advantage, consistency, interaction quality).
no_budget_pressure   - budget no longer matters; optimize for power/theme.
agent_choice         - agent decides from power bracket, goals, and deck context.
```

For `value_based_overage`, the agent must explain why the over-budget upgrade is worth considering.

### Budget Upgrade Review

Trigger when the deck is meaningfully under budget (especially T1/T2). Show:

```text
current estimated deck cost
stated budget
unused budget
budget utilization percentage
upgrade options under budget
over-budget high-impact options (only if truly worth it)
```

Label every option:

```text
Under budget
Within 10% overage
Over budget - high-impact option
Over budget - not recommended
```

Do not show weak over-budget upgrades. Do not recommend a card only because it is expensive — a generic expensive staple that does not strongly improve the deck is not shown.

Ask before applying upgrades (unless the user already gave permission):

```text
What do you want to do?

A. Keep the deck at the current lower cost.
B. Apply only upgrades that stay under the stated budget.
C. Apply upgrades up to the normal 10% overage if they are worth it.
D. Show me the over-budget high-impact options before deciding.
E. Apply only the highest-impact upgrade package, even if it goes slightly over budget.
F. Agent choice.
```

```text
A -> keep deck as-is.
B -> do not exceed budget.
C -> allow default overage (10%).
D -> show over-budget options but do not apply yet.
E -> apply only upgrades with strong value justification.
F -> choose based on power bracket and user intent.
```

Never auto-apply over-budget upgrades without user approval. Do not final-build before the Budget Upgrade Review decision is resolved when review is triggered.

### Power Bracket Behavior

```text
T1/T2: actively search meaningful upgrades; show strong under-budget upgrades and
       over-budget high-impact options worth considering.
T3:    prefer staying under budget; show over-budget options only if user allowed
       value-based overage or the card strongly supports the commander.
T4:    do not push over budget unless the user explicitly asks; keep precon-level intent.
```

### Upgrade Recommendation Quality

Every upgrade recommendation must include:

```text
old card
new card
old price
new price
cost difference
new estimated deck total
under budget or over budget (with label)
why it improves the deck
package/role it improves
risk/downside
```

A recommended upgrade must improve at least one: commander synergy, engine strength, win condition, ramp quality, mana base speed, draw/card advantage, protection, interaction, consistency, power bracket fit.

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
