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
12. A stated budget is a SPENDING PLAN as well as a ceiling: draft TO it (target
    85–100% utilization) and never past it. Landing far under budget is a drafting
    failure, not prudence (§11).
13. Before starting the build ask the user "Do you want to clear output folder? "(Yes/No - answere only) if user selects yes run(.venv/bin/mtg temp-clean --full --yes) to clear output folder using the mtg tool. if user select no, then skip and continue to build
14. The §5 core questions are UNCONDITIONAL: ask them and WAIT for the user's answers
    before drafting a single card. "Ask if in doubt" is not the contract — an agent with
    plausible defaults never has doubts, and its defaults are not answers. `deck-add`
    enforces this mechanically: its FIRST call refuses to create a deck without the
    answered contract (`--set-config budget=<USD|n/a> --set-config bracket=<1-5|n/a>`).
    A build that drafts without asking is not following this document.

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
output/build-notes.json
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

**MANDATORY — ask the 4 core questions and WAIT for the answers before building** (rule 14).
This is unconditional: it does not depend on the agent having doubts, and plausible
defaults are not answers (`Agent choice` must be the user's pick, never the agent's
assumption). Use multiple choice and always include `Agent choice`. Enforcement:
`deck-add`'s first call refuses to create a deck until the answered contract
(budget + bracket) is passed via `--set-config`, so a draft cannot mechanically start
before this step. If the user already answered something in their request, don't
re-ask it — but the remaining core questions still get asked.

**Core question 1 asks for the official Commander BRACKET (1-2 / 3 / 4-5), always with
an `n/a — I don't care about brackets` option** (default n/a: brackets are a social
contract, not a requirement). With a bracket target, `mtg deck-power --bracket <N>`
must report COMPLIANT before finalizing (deterministic criteria: Game Changers count,
mass land denial, extra turns, 2-card combos); with n/a, skip the verdict and just
show the TIER (consider-only). See agents/user-feedback.md for the exact wording and
the bracket→power-level mapping for category-counts.

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

Use this flow unless the user gives a narrower task.

### 6.0 The annotated-deck flow (PRIMARY since the Consistency Engine)

The draft is built THROUGH the tool, package by package — never held in agent
memory. Every card enters with its purpose, every combo gets noted when spotted,
and the finished build ships with its judgment.

```bash
# 1. Analyze, plan, shortlist (unchanged: commander-analyze, category-counts, search-tags)
# 2. Draft by PACKAGE — deck-add validates at entry (exists/color/singleton/size),
#    annotates the purpose, and prints the batch price + RUNNING TOTAL with budget %:
mtg deck-add --deck output/deck.json --commander "<Commander>" \
  --cards "Sol Ring;Arcane Signet;..." --purpose ramp \
  --set-config budget=150 --set-config budget_mode=soft --set-config bracket=n/a \
  --deck-note "<theme / gameplan>"        # first call creates the deck + contract
mtg deck-add --deck output/deck.json --cards "..." --purpose draw     # ~8-12 packages total
mtg deck-add --deck output/deck.json --cards "12 Mountain;11 Plains" --purpose flex

# 3. WHILE drafting: note combos the moment you see them (the carpenter's tally)
mtg note "<what you saw>" --type combo --cards "A;B" --combo-class infinite
#    ...and note REJECTED candidates too (--type decision) — that evaluation work
#    is what the Budget Upgrade Review re-pays when it isn't recorded.

# 4. One annotation pass at the END of the draft (never per-card-per-add):
mtg deck-annotate --deck output/deck.json --auto                      # census seeds ~85%
mtg deck-annotate --deck output/deck.json --cards "A;B" --purpose-add synergy --note "..."
mtg deck-annotate --deck output/deck.json --sync-notes                # combos -> deck

# 5. Inspect and score:
mtg deck-view  --deck output/deck.json [--by-purpose | --card "Name"]
mtg deck-power --deck output/deck.json --commander "<Commander>"     # consistency tier
#    (bracket target reads from the deck's config; n/a skips the compliance verdict)

# 6. Close as always: deck-fill-lands, validate, deck-check, deck-gaps, preflight,
#    final-build (the build folder ships deck_list.json — the annotated judgment).
```

The legacy decklist.txt path below still works (deck-write converts it), but it
loses entry-time validation, running budget, and purposes — prefer deck-add.

### 6.1 Legacy flow reference

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

Optional context: if the build wants combo/synergy ideas beyond what the analyzer
surfaces, research the web yourself (see §12) and record findings with `mtg note` —
there is no fetch command for this (removed in v0.8.0).

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
mtg prices-batch --name "Card A" --name "Card B"          # cost hand-picked candidates BEFORE they join the list (known-price total included)
mtg deck-swap --deck output/decklist.txt --commander "<Commander>" --swap "Old=New"
mtg note "<finding>" [--type combo --cards "A;B" --combo-class infinite]   # building notes: RECORD combos/decisions while drafting, don't memorize them
mtg deck-power --deck output/deck.json --commander "<Commander>" [--bracket <N>]   # the two categorizers: bracket compliance + tier (consider-only)
```

**Building notes (the carpenter's tally):** whenever you SPOT a combo or make a
non-obvious decision while drafting, record it immediately with `mtg note` — combo
notes (`--type combo --cards "A;B" --combo-class infinite|non_infinite|utility|auto_win`;
`;` separates names because card names contain commas) become first-class combo
sources for `deck-power`, deduped against the external fetch. Notes live in
`output/build-notes.json`.

**Before finalizing, run `mtg deck-power`:** if the user chose a bracket target, its
compliance verdict must be COMPLIANT (deterministic: Game Changers, MLD, extra turns,
2-card combos); the TIER (synergy + combos + game changers, 0-10 in 0.5 bands, F
below 5.0) is CONSIDER-ONLY — report it, never gate on it, and its "one card away"
combo list is a lead in both directions (add the finisher, or stay clear of it at
low brackets).

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

### 7.0b Archetype: `analyzer.archetype_support` is the read

`commander_analysis.json` carries a SINGLE, evidence-first archetype read:

- **`analyzer`** — `archetype_support` as ordinal bands (`very_high/high/medium/low`), plus
  `signals` (detected feature IDs), `dominant_symmetry`, and `warnings`. Every band is backed by
  detected evidence; run `mtg analyze-card "<Commander>"` if you need the full traces (which rule
  fired on which text). `best_archetype` is derived from the top band; `analyzer.tags`
  (+ `analyzer.signals`) is the functional-tag vocabulary.

The legacy keyword-scored reads (`archetype_fit`, `commander_tags`, `synergy_tags`,
`anti_synergy_tags`) and the `legacy_deprecations` block were **REMOVED in v0.8.0** — there is no
longer a competing numeric ranking to reconcile. Use `analyzer.archetype_support` /
`analyzer.tags` / `best_archetype` directly.

**Toolbox commanders:** if `archetype_support` includes `Toolbox / Goodstuff` (or the analyzer
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
- **By popularity (consider-only)** — `--max-rank <N>` on `search`/`search-tags` caps candidates
  by EDHREC rank (unknown ranks are kept). Popularity ≠ power: use it to surface format staples
  at high brackets, never as an include-verdict. `deck-check` reports the deck's `staple_density`
  (median rank, % top-2000) as an INFORMATIONAL line — it never warns and never gates preflight;
  synergy-dense decks read low by design.
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
each gap — plus hook-specific gaps (e.g. a custom-counter commander with no proliferate). It also
runs a **Commander plan check**: for every high/very_high band in `analyzer.archetype_support` it
counts the deck cards that actually serve that plan and reports a `plan_gap` (JSON keys:
`analyzer_support`, `plan_gaps`; each gap carries a ready fill command). A plan gap means the deck
ignores what the commander's own text says it wants — treat it as a first-class finding. Run it
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

**A budget is a spending plan, not just a cap.** The user chose that number expecting a
deck of roughly that quality — build TO it from the FIRST draft, not up to it through a
review afterwards. The ceiling is still absolute (never exceed a hard budget), but
inside the ceiling the money is there to be spent on the deck's plan.

```text
DRAFT-TO-BUDGET (the primary rule):
  Target 85–100% utilization in the first draft. Landing far under budget is a
  drafting failure — it means the cheapest functional card was picked in slots where
  a strictly better card was affordable.
Allocate while drafting, not after: think in package budgets (e.g. mana base ~20-30%,
  draw engines ~15%, the commander's core plan ~30%, interaction/protection ~15%).
  When two cards fill the same slot, take the strongest one the slot's share affords —
  not the cheapest one that functions.
Price visibility at pick time (full build #3 lesson): NEVER sum a draft on memory
  prices. Search-family results print each card's price; for hand-picked staples run
  `mtg prices-batch --name "A" --name "B" ...` (known-price total included) BEFORE
  adding them to the list — memory prices measured off by 5x (Flawless Maneuver).
Per-card price instinct: do NOT self-impose tiny caps. On a $75 budget a $2/card cap
  is self-sabotage. A key slot (win condition, draw engine, signature synergy piece)
  may reasonably eat 10–20% of the budget alone; the --by-card high-cost flag (>20%)
  exists for VISIBILITY, not prohibition. Derive search caps from the budget
  (--max-price ≈ budget × 0.15–0.20 for key-slot shortlists), not from habit.
Quality bar unchanged: an expensive card that does not strongly improve the deck is
  still not an upgrade — spend on the PLAN, not on price tags.
Utilization floor (the FAILSAFE, not the mechanism): if the finished deck still sits
  under ~60% of budget, the Budget Upgrade Review below is REQUIRED before finalizing.
  If drafting followed this contract, the review should rarely trigger.
Default overage allowance is 10% (soft budgets only).
Unknown price means unknown, not free and not forbidden.
```

Use:

```bash
mtg budget output/deck.json --budget <amount> --overage 10 --json-output
```

### Budget Reallocation (the cost-by-type lens)

`budget --by-card` answers "which CARD is expensive"; `deck-view`'s **cost by type**
(human line, or `metrics.price_by_type` in JSON) answers "where does the MONEY sit"
— and money sitting in a low-impact bucket is budget a higher-impact slot could use.

When to run the check: the deck is over budget, a wanted upgrade doesn't fit, or a
trim is needed for any reason.

```bash
mtg deck-view --deck output/deck.json          # "cost by type: creature=$45, land=$31, ..."
```

The classic finding: a large share of budget in LANDS (expensive duals/utility lands)
while a win condition, draw engine, or key synergy piece was passed on for price.
Swapping nonbasic lands for basics frees that money — at a real cost in mana
consistency (cheap in mono/2-color decks, increasingly risky in 3+ colors).

**Rule: NEVER reallocate silently — ASK.** This is a personal-preference trade the
user owns (they may value the mana base, already own those lands, or see something
the agent didn't). Present a concrete proposal:

```text
Cost by type shows $31 on lands. Swapping <Land A, Land B, Land C> for basics
frees ~$18, enough for <Upgrade X> ($15). Trade-off: slightly less consistent
mana (this is a 2-color deck — low risk).

a) Keep the mana base as is — find the money elsewhere (or skip the upgrade)
b) Swap the listed lands for basics and apply the upgrade
c) Partial — swap only the lands I name, then re-check
d) Agent choice
```

Every proposal must name the exact cuts, the exact upgrade, both prices, the freed
amount, and the consistency trade-off. Apply via `mtg deck-swap` (never hand-edit),
then re-run `budget` and `deck-view` to confirm the landing. The same lens works in
reverse for any type bucket (e.g. $40 in creatures on a spellslinger plan is the
same conversation).

### Owned cards (user-bulk): they cost the budget $0

`user-bulk/collection.txt` holds the cards the user already OWNS (maintained with
`mtg bulk-add`, or edited by hand — see `user-bulk/README.md`). `mtg budget` and
preflight's budget gate automatically exclude owned copies from the bill (up to the
owned quantity) and show it on a visible `Owned (user-bulk)` line; `--no-bulk`
disables per run.

Agent rules:
- In Detailed Build mode (or when the user mentions owning cards), ask ONCE whether
  they have a collection to record; if yes, help them load it with `mtg bulk-add`
  (validated, fuzzy did-you-mean) before budgeting.
- An owned expensive staple is FREE for this deck — prefer it over buying a weaker
  substitute; the budget freed is real money for other slots (draft-TO-budget
  applies to the BILLED total, not the sticker total).
- Never assume ownership: only what's in the collection file counts.

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

Trigger when the deck is meaningfully under budget — concretely, whenever budget
utilization is below ~60% (more than 40% of the budget unused), and especially at T1/T2.
Below that floor the review is REQUIRED before finalizing: the user's budget number is a
quality expectation, and a deck that ignores 40%+ of it almost certainly took the cheapest
option in slots where a strictly better card was affordable. Show:

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

## 12. Combo & Synergy Research Contract

The former `explore` / `combos` commands were REMOVED in v0.8.0 (they fetched from
external community sites without permission — a liability for the tool). **Combo and
high-synergy research is the AGENT's job now:**

1. First exhaust the local tool: `commander-analyze` (archetype bands, oracle hooks,
   `wanted_card_patterns`), `search-tags`, `similar` / `complements` — most synergy
   packages come straight from these.
2. If the build genuinely needs outside ideas (combo lines, meta staples for the
   commander), use your own web search — cite what you found and VERIFY every card
   against the local DB before considering it (`mtg card` / `cards-batch --verify`;
   never trust remembered lists).
3. **Record what you adopt with `mtg note`**: combos as
   `--type combo --cards "A;B" --combo-class ...` (they become first-class
   `deck-power` sources), rejected ideas as `--type decision`.

Rules (unchanged):

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
