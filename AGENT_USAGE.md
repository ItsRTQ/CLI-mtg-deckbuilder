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

Default maximum: 3 questions before deckbuilding.

Important questions:

```text
power level
budget
build direction if commander has multiple paths
specific include/exclude cards or effects
combo policy
tutor policy
mana base quality
```

If the user does not answer, choose a reasonable option and continue.

---

## CLI Workflow

Typical commands:

```bash
mtg card "<commander>" --json-output
mtg search "<query>" --colors "<colors>" --limit 30 --json-output
mtg suggest --commander "<commander>" --role ramp --limit 30 --json-output
mtg suggest --commander "<commander>" --role card_draw --limit 30 --json-output
mtg suggest --commander "<commander>" --role removal --limit 30 --json-output
mtg suggest --commander "<commander>" --role protection --limit 30 --json-output
mtg suggest --commander "<commander>" --role synergy --limit 60 --json-output
mtg suggest-lands --commander "<commander>" --count <count> --json-output
mtg validate --commander "<commander>" --deck output/deck.json --json-output
mtg deck-check --commander "<commander>" --deck output/deck.json --json-output
mtg enrich output/deck.json --output output/deck.enriched.json
mtg export output/deck.json --output output/deck.moxfield.txt
```

If package-aware commands exist, prefer them. If not, use `search` and normal `suggest` to approximate package searches.

---

## Required Build Steps

1. Parse user request.
2. Ask user-feedback questions if useful.
3. Look up commander with CLI.
4. Confirm legality and commander eligibility.
5. Analyze commander engine.
6. Detect archetype/detail/constraints.
7. Build package plan.
8. Search candidates by role and package.
9. Rank candidates.
10. Build 100-card deck.
11. Save `output/deck.json`.
12. Validate.
13. Fix errors.
14. Run deck-check.
15. Fix major coherence issues.
16. Export only after validation passes.
17. Explain deck.

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
