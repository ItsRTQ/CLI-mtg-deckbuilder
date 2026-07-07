# BUFF

Mode guide for improving an existing MTG Commander deck.

`BUFF.md` is a different workflow from `BUILDER.md`.

- `BUILDER.md` = build a new deck from scratch.
- `BUFF.md` = analyze an existing deck, find weak points, ask the user what to improve, then upgrade the deck with user approval.

Read `BUILDER.md` first. All non-negotiable rules from `BUILDER.md` still apply unless this file gives a stricter rule for buffing an existing deck.

The local `mtg` CLI remains the source of truth for card data, legality, prices, power/toughness, oracle text, validation, search, suggestions, deck-check, budget, export, and final-build saving.

---

## 1. Core Purpose

This mode improves a deck the user already has.

The agent must not assume the user wants a full rebuild.

The goal is:

```text
understand the current deck
preserve the user's intended identity when possible
identify weak/off-plan cards
ask what the user wants to improve
suggest replacements with clear reasons
apply only approved changes
validate the improved deck
explain what changed and how to play it
```

---

## 2. Non-Negotiable Rules

1. Do not invent cards, card text, prices, legality, power, toughness, or color identity.
2. Do not use cards outside the commander's color identity.
3. Do not use Commander-illegal cards.
4. Do not create helper scripts.
5. Do not edit source code, seeds, `.env`, README, `BUILDER.md`, or agent files during deck improvement.
6. Do not modify the user's original deck file unless the user explicitly asks.
7. Preserve the original deck identity unless the user approves a direction change.
8. Do not replace pet cards, theme cards, or weird cards until asking if their purpose is unclear.
9. Do not final-build until the improved deck passes `mtg validate`.
10. Do not save a final improved build unless the user approves the replacement plan or selected changes.
11. `synergy` is not a role. Never use `--role synergy`. Use `--synergy` on a real role.
12. Commander-zone cards are metadata, not `main_deck` cards.

---

## 3. Allowed BUFF Artifacts

The agent may create/update these during deck improvement:

```text
output/buff_input_decklist.txt
output/buff_original_deck.json
output/buff_original_analysis.json
output/buff_cut_candidates.md
output/buff_upgrade_plan.md
output/buff_change_log.md
output/deck.json
output/deck.enriched.json
output/deck.moxfield.txt
output/deck_explanation.md
output/validation_report.json
output/commander_analysis.json
output/commander_combos.json
final-builds/<build-name>/
```

Avoid changing the user-provided source file. Work from a copy in `output/`.

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

If a needed CLI feature is missing, continue as far as possible and report it in **Build Feedback**.

---

## 4. BUFF Input

The user may provide a decklist in either way:

```text
1. pasted directly in chat
2. file path at the repo root
```

Examples:

```text
buff this deck:
1 Sol Ring
1 Arcane Signet
...
1 Edgar Markov
```

or:

```text
buff decklists/edgar_markov.txt
```

When the user points to a file:

- read the file
- do not overwrite it
- copy/convert it into `output/buff_input_decklist.txt`

---

## 5. High-Level Workflow

Use this flow:

```text
1. Ingest decklist.
2. Convert to structured deck JSON.
3. Identify commander / partner commander.
4. Validate the original deck.
5. Analyze commander.
6. Analyze current deck infrastructure.
7. Detect deck identity and likely plan.
8. Identify strengths.
9. Identify weaknesses.
10. Identify cut candidates and questionable cards.
11. Ask user what they want to improve.
12. Ask budget/tolerance if needed.
13. Generate replacement/upgrade plan.
14. Ask user approval before applying changes.
15. Apply approved changes.
16. Re-run validation, deck-check, and budget-check.
17. Create explanation / change guide.
18. Final-build only if user wants a finalized improved version.
19. Report Build Feedback if friction happened.
```

---

## 6. Step 1: Ingest and Convert Deck

If the decklist is text, save a copy:

```text
output/buff_input_decklist.txt
```

Convert with:

```bash
mtg deck-write \
  --input output/buff_input_decklist.txt \
  --output output/buff_original_deck.json \
  --commander "<Commander>" \
  --structured \
  --force
```

If the commander is not known, infer from the list only if obvious. If not obvious, ask:

```text
Which commander is this deck using?

a) <candidate commander>
b) <candidate commander>
c) I will provide the commander name
d) Agent choice if obvious
```

Do not guess silently when multiple commanders could be valid.

For partner decks, use `--partner`.

After conversion, work from a copy. Do not modify the original deck file.

---

## 7. Step 2: Validate Original Deck

Run:

```bash
mtg validate --commander "<Commander>" --deck output/buff_original_deck.json --json-output
```

Partner:

```bash
mtg validate \
  --commander "<Commander A>" \
  --partner "<Commander B>" \
  --deck output/buff_original_deck.json \
  --json-output
```

If validation fails, classify errors:

```text
blocking errors
warning-level issues
decklist formatting issues
missing/misspelled cards
color identity violations
deck size issues
singleton violations
commander metadata issues
```

Ask the user before making structural fixes if the issue could reflect intentional choice or decklist export weirdness.

---

## 8. Step 3: Analyze Commander

Run:

```bash
mtg commander-analyze \
  --commander "<Commander>" \
  --output output/commander_analysis.json \
  --json-output
```

Use the analysis to understand:

```text
color identity
type line / subtypes / creature types
power/toughness
text signals
commander tags
synergy tags
engine profile
archetype fit
role pressures
provides / requires / rewards
wanted card patterns
avoid card patterns
```

For partner decks, include `--partner`.

Do not invent commander data. Use the CLI output.

---

## 9. Step 4: Analyze Current Deck Identity

The agent must understand what the deck is already trying to do before improving it.

Analyze:

```text
commander gameplan
main archetype
subtheme / detail
power bracket estimate
deck speed
mana curve
land count
ramp count
card draw count
removal count
board wipes
protection
recursion
tutors
win conditions
combo presence
synergy enablers
synergy payoffs
dead/filler cards
off-theme cards
mana base quality
budget status if budget exists
```

Use CLI tools where useful:

```bash
mtg category-counts \
  --commander "<Commander>" \
  --archetype "<Detected Archetype>" \
  --power-level <estimated or user-provided number> \
  --philosophy "<detected or user-provided philosophy>" \
  --analysis output/commander_analysis.json \
  --json-output

mtg deck-check --commander "<Commander>" --deck output/buff_original_deck.json --json-output
mtg prices-batch output/buff_original_deck.json --json-output
```

If a command output seems wrong, do not blindly follow it. Use judgment and report friction.

---

## 10. Step 5: Find Weaknesses and Cut Candidates

Start the weakness pass with the CLI's own audit — it compares the deck against the commander's
plan and reports thin categories with ready fill-commands:

```bash
mtg deck-gaps --deck output/buff_deck.json --commander "<name>" --archetype <arch> --json-output
```

Treat its gaps as leads to judge, not automatic conclusions. Its `plan_gaps` section (analyzer plan check) is the strongest lead: the deck is ignoring what the commander's own text wants — and each audited band now LISTS the cards it counted (`analyzer_support[].cards`), so judge the lead against the actual list, not the number alone. Then, for cuts, `mtg similar
"<card>"` finds functional replacements, and every swap goes through `mtg deck-swap` (validates
the incoming card before writing — never edit the list manually).

Identify cards that may be:

```text
filler
off-plan
too low impact
too expensive for their effect
too slow for the target power level
wrong role
redundant beyond useful amount
anti-synergistic
outside the apparent theme
generic goodstuff that does not support the plan
weak ramp
weak card draw
weak protection
weak removal
weak win condition
```

Also identify questionable cards:

```text
cards that look weird but may have a hidden purpose
pet cards
meta calls
combo pieces
budget replacements
flavor/theme choices
cards that work only with another card in the deck
```

Never cut questionable cards automatically. Ask the user.

---

## 11. Weakness Report Format

Before improving, show the user a table.

Use this structure:

```text
## Current Deck Read

Commander: <Commander>
Detected plan: <archetype/theme>
Estimated power: <T bracket or estimate>
Main strengths: <brief>
Main weaknesses: <brief>
Validation status: <pass/fail>
Budget status: <if known>
```

Then:

| Card | Current role | Issue | Recommendation | Ask user? |
|---|---|---|---|---|
| Card A | Ramp | Too slow / tapped / off-plan | Replace | No |
| Card B | Theme piece | Weird but possibly intentional | Ask purpose | Yes |
| Card C | Payoff | Low impact | Replace if user wants stronger build | Maybe |

Keep the summary brief. Give enough detail to let the user decide.

---

## 12. Required User Question After Analysis

After the weakness report, ask:

```text
What do you want to improve first?

a) Ramp / mana speed
b) Card draw / card advantage
c) Interaction / removal
d) Protection / resilience
e) Commander engine / synergy
f) Win conditions
g) Add or improve combos
h) Mana base
i) Everything / full tune-up
j) Keep the current identity but remove weak cards
k) Agent choice
```

Also ask about cards marked questionable:

```text
These cards look unusual in the current build. What should I do with them?

a) Keep them; they are pet/meta/theme cards
b) Replace them if better options exist
c) Ask me one by one
d) Agent choice
```

If budget is not known, ask:

```text
What budget should I use for upgrades?

a) No new spending / use similar price replacements
b) $25 upgrade budget
c) $50 upgrade budget
d) $100 upgrade budget
e) Custom budget
f) No budget pressure
g) Agent choice
```

If budget exists, ask budget tolerance when needed:

```text
How strict is the upgrade budget?

a) Hard budget — do not go over
b) Soft budget — up to 10% over is okay if meaningful
c) Value-based overage — over is okay only for major upgrades
d) Flexible — optimize first, keep price reasonable
e) Agent choice
```

---

## 13. Replacement Planning

Generate replacements only after user direction is clear.

For each suggested swap, include:

```text
old card
new card
old price
new price
cost difference
new estimated deck total
role/package improved
why it is better
what risk/downside it has
whether it stays under budget
```

Use current CLI tools:

```bash
mtg suggest --commander "<Commander>" --role ramp --json-output
mtg suggest --commander "<Commander>" --role card_draw --json-output
mtg suggest --commander "<Commander>" --role protection --synergy --analysis output/commander_analysis.json --json-output
mtg suggest --commander "<Commander>" --role removal --json-output
mtg suggest --commander "<Commander>" --role engine --synergy --analysis output/commander_analysis.json --json-output
mtg suggest --commander "<Commander>" --role payoff --synergy --analysis output/commander_analysis.json --json-output
mtg search --oracle "draw a card" --type creature --json-output
mtg search --oracle "can't be blocked" --oracle target --oracle creature --json-output
mtg explore --commander "<Commander>" --json-output
mtg combos --commander "<Commander>" --output output/commander_combos.json --json-output
```

Use `--type` when the user needs an effect on a specific card type.

Use `--synergy` when the replacement must connect to the commander.

Do not use `--role synergy`.

---

## 14. Approval Gate

Do not apply replacements until the user approves.

Show a proposed change plan:

| Change | Cost change | New total | Why | Risk |
|---|---:|---:|---|---|
| Old A -> New A | +$8 | ~$148 | Better protection | Higher mana cost |
| Old B -> New B | -$2 | ~$146 | Cleaner ramp | Less flavor |

Ask:

```text
How should I apply these changes?

a) Apply all recommended changes
b) Apply only budget-safe changes
c) Apply only synergy/engine changes
d) Apply only ramp/mana base changes
e) Let me approve swaps one by one
f) Make no changes; just give me the analysis
g) Agent choice
```

If user chooses one-by-one, ask concise per-card approval.

---

## 15. Apply Approved Changes

After approval:

1. Update the working deck only.
2. Keep original deck copy unchanged.
3. Write the improved deck to:

```text
output/deck.json
```

4. Re-run validation.
5. Re-run deck-check.
6. Re-run budget-check if budget exists.

Do not final-build until validation passes.

---

## 16. Budget Upgrade Review in BUFF Mode

If upgrades leave significant unused budget, or if the user asked for high-power improvements, run Budget Upgrade Review using `BUILDER.md` rules.

For over-budget upgrades:

- show them only if they create strong value
- do not apply without user approval
- label them clearly

Labels:

```text
Under budget
Within 10% overage
Over budget - high-impact option
Over budget - not recommended
```

Never recommend expensive cards only because they are expensive.

---

## 17. Combos in BUFF Mode

Use `mtg combos` only as context.

If user wants combos:

```text
identify compact packages
check bracket/power appropriateness
verify legality and color identity
show the package before adding
```

If user does not want combos:

```text
avoid adding full combo lines accidentally
individual combo pieces may still be useful if they fit the deck naturally
```

Ask before adding full combos.

---

## 18. Final Explanation / Buff Guide

After approved changes and validation, write:

```text
output/deck_explanation.md
```

Use this structure:

```text
# Buffed Deck Guide: <Commander> - <Theme>

## Summary
## Original Deck Read
## User Improvement Goals
## Key Changes Made
## Cards Removed
## Cards Added
## Package Improvements
## How the Deck Plays Now
## Win Conditions
## Budget Status
## Validation Status
## Remaining Weaknesses
## Optional Future Upgrades
## Build Feedback
```

If changes were small, keep the guide brief.

If the deck changed significantly, explain how the gameplan changed.

---

## 19. Final Build Saving

Ask before saving a final buffed build.

If user approves, use:

```bash
mtg final-build \
  --deck output/deck.json \
  --commander "<Commander>" \
  --theme "<Theme>-Buffed" \
  --bracket <Bracket> \
  --explanation output/deck_explanation.md
```

The final folder should contain the improved decklist and explanation.

Do not overwrite the original user deck file.

---

## 20. Build Feedback

At the end, include Build Feedback only if useful.

Good feedback examples:

```text
Search friction: suggest returned off-role cards.
Validation friction: original deck had command-zone cards inside main_deck.
Budget friction: several upgrade candidates had unknown prices.
Tag gap: tool had weak support for this archetype.
User-input gap: unclear whether questionable cards were pet cards or mistakes.
```

Also provide constructive improvement suggestions for future deck buffing:

```text
Better tags for X would improve replacement quality.
A deck-diff command would speed up buff review.
Batch role analysis would reduce manual card review.
```

If the buff went smoothly, do not invent feedback.

---

## 21. Output Discipline

When acting in BUFF mode:

- Be brief but clear.
- Show tables for analysis and proposed swaps.
- Ask user approval before changing deck content.
- Never bury important warnings.
- Do not present unvalidated decks as final.
- Do not confuse analysis candidates with approved changes.

The agent should help the user improve the deck, not take control away from them.
